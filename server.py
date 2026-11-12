"""Daywell local Python server. No third-party runtime dependencies required.

The existing Daywell SQLite schema is retained. API compatibility lets the same
browser features use the Python implementation without rewriting saved records.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, unquote, parse_qs
import uuid
from core import (APIError, COLLECTIONS, DEFAULTS, object_value, fail, validate,
                  validate_state, validate_settings, date, advance_date,
                  csv_cell, fingerprint, integer)
from account_gateway import AccountGateway

ROOT=Path(__file__).resolve().parent
# A Content Security Policy limits what scripts and connections the local page can use.
CSP="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

# Convert Python values to compact JSON without silently accepting invalid numbers.
def json_text(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)

# Own the local database and all application actions.
class DaywellApp:
    # Set up local folders, open SQLite, and prepare optional helper features.
    def __init__(self,data_dir=None,public_dir=None,helper=True):
        self.data_dir=Path(data_dir or os.environ.get('DAYWELL_PYTHON_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'/'share'))/'DaywellPython')
        self.dataDir=self.data_dir
        self.data_dir.mkdir(parents=True,exist_ok=True)
        self.backup_dir=self.data_dir/'backups';self.backup_dir.mkdir(exist_ok=True)
        self.public_dir=Path(public_dir or ROOT/'public').resolve()
        self.lock=threading.RLock()
        self.db=sqlite3.connect(self.data_dir/'daywell.sqlite',isolation_level=None,check_same_thread=False,timeout=30)
        self.db.row_factory=sqlite3.Row
        self.db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(kind,id)); CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT NOT NULL); CREATE TABLE IF NOT EXISTS payments (key TEXT PRIMARY KEY,body TEXT NOT NULL);')
        self.daily_backup()
        self.helper=None
        if helper:
            from helper import HelperService
            self.helper=HelperService(self)

    # Read all saved items in one collection from SQLite.
    def get(self,kind):
        return [json.loads(row['body']) for row in self.db.execute('SELECT body FROM records WHERE kind=? ORDER BY rowid',(kind,))]

    # Read private app metadata such as settings or import receipts.
    def get_meta(self,key,default=None):
        row=self.db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone()
        return json.loads(row['value']) if row else default

    # Insert or update one metadata value.
    def set_meta(self,key,value):
        self.db.execute('INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json_text(value)))

    # Return saved preferences, or defaults for a new workspace.
    def settings(self): return self.get_meta('settings',DEFAULTS.copy())
    # Assemble the complete state the browser needs to render each page.
    def state(self): return dict(settings=self.settings(),**{kind:self.get(kind) for kind in COLLECTIONS})
    # Add internal history to downloadable backups without exposing it in the normal page state.
    def export_state(self):
        metadata={row['key']:json.loads(row['value']) for row in self.db.execute("SELECT key,value FROM meta WHERE key!='settings'")}
        payments={row['key']:json.loads(row['body']) for row in self.db.execute('SELECT key,body FROM payments')}
        return {**self.state(),'_daywell':{'version':1,'metadata':metadata,'payments':payments}}
    # Insert or update one validated record by its ID.
    def save(self,kind,item):
        self.db.execute('INSERT INTO records(kind,id,body) VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body',(kind,item['id'],json_text(item)))
        return item
    # Run related database writes together; roll everything back on error.
    def transaction(self,callback):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                result=callback();self.db.execute('COMMIT');return result
            except BaseException:
                self.db.execute('ROLLBACK');raise
    # Write both a readable JSON export and a complete SQLite backup.
    def backup(self,label):
        # JSON remains export-compatible; sqlite backup additionally preserves
        # import receipts, bill idempotency and helper undo metadata.
        name=re.sub(r'[^a-zA-Z0-9_.-]','-',str(label))
        path=self.backup_dir/(name+'.json')
        with path.open('x',encoding='utf-8') as file: json.dump(self.export_state(),file,ensure_ascii=False,indent=2,allow_nan=False)
        sqlite_path=self.backup_dir/(name+'.sqlite')
        target=sqlite3.connect(sqlite_path)
        try:self.db.backup(target)
        finally:target.close()
        return str(path)
    # Keep one automatic backup per day before new work starts.
    def daily_backup(self):
        label='daily-'+dt.date.today().isoformat()
        if not (self.backup_dir/(label+'.json')).exists():self.backup(label)
    # Make a uniquely named snapshot before a risky change.
    def recovery_backup(self,label):return self.backup(label+'-'+str(time.time_ns())+'-'+str(uuid.uuid4()))
    # Release the database connection when the server stops.
    def close(self):self.db.close()

    # Read statement import history used for duplicate checks and undo.
    def receipts(self):
        return [json.loads(r['value']) for r in self.db.execute("SELECT value FROM meta WHERE key LIKE 'statement-import:%' ORDER BY rowid DESC")]

    # Handle statement preview confirmation, duplicate checks, history, and undo.
    def statements(self,method,path,body):
        if method=='GET' and path=='/api/imports':
            return 200,[{**{k:v for k,v in r.items() if k!='entries'},'count':len(r['entries']),'months':list(dict.fromkeys(e['date'][:7] for e in r['entries']))} for r in self.receipts()]
        if method=='POST' and path=='/api/import/commit':
            body=object_value(body);file_hash=body.get('fileHash')
            if not isinstance(file_hash,str) or not re.fullmatch('[a-f0-9]{64}',file_hash):fail('Choose a statement file first.')
            if body.get('currency')!=self.settings()['currency']:fail('Your workspace currency changed. Reopen the import and review it.')
            if not isinstance(body.get('rows'),list) or not 1<=len(body['rows'])<=5000:fail('Select between 1 and 5,000 expenses.')
            indices=set();rows=[]
            for raw in body['rows']:
                object_value(raw);index=raw.get('index')
                if not integer(index) or not 0<=index<=100000 or index in indices:fail('Invalid statement row.')
                indices.add(index)
                if raw.get('type')!='expense':fail('Only expenses can be imported here.')
                identifier='stmt-'+hashlib.sha256((file_hash+':'+str(index)).encode()).hexdigest()
                rows.append((validate('transactions',{**raw,'id':identifier}),raw.get('allowDuplicate') is True))
            receipts=[r for r in self.receipts() if not r.get('undone') and r['entries']]
            same=next((r for r in receipts if r.get('fileHash')==file_hash),None)
            if same:return 200,{'id':same['id'],'added':0,'skipped':len(rows)}
            months={item['date'][:7] for item,_ in rows}
            if body.get('allowMonthOverlap') is not True and any(e['date'][:7] in months for r in receipts for e in r['entries']):fail('A statement has already been imported for this month. Confirm that this is a different statement before continuing.')
            self.recovery_backup('before-statement-import')
            # Save all confirmed statement rows as one atomic database transaction.
            def commit():
                current=self.get('transactions');ids={r['id'] for r in current};keys={fingerprint(r) for r in current};entries=[];skipped=0
                for item,allow in rows:
                    key=fingerprint(item)
                    if item['id'] in ids or (not allow and key in keys):skipped+=1;continue
                    self.save('transactions',item);ids.add(item['id']);keys.add(key);entries.append(item)
                receipt={'id':str(uuid.uuid4()),'created':dt.datetime.now(dt.timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'),'currency':body['currency'],'fileHash':file_hash,'entries':entries,'skipped':skipped,'undone':False}
                self.set_meta('statement-import:'+receipt['id'],receipt)
                return {'id':receipt['id'],'added':len(entries),'skipped':skipped}
            return 200,self.transaction(commit)
        if method=='POST' and path=='/api/import/undo':
            body=object_value(body)
            if not isinstance(body.get('id'),str):fail('Choose an import to undo.')
            receipt=self.get_meta('statement-import:'+body['id'])
            if not receipt:fail('Import not found.')
            if receipt.get('undone'):return 200,{'removed':0,'kept':0,'alreadyUndone':True}
            self.recovery_backup('before-undo-import')
            # Reverse an import only when the recorded rows still match its receipt.
            def undo():
                current={t['id']:t for t in self.get('transactions')};removed=kept=0
                for item in receipt['entries']:
                    now=current.get(item['id'])
                    if now is None:continue
                    if now!=item:kept+=1;continue
                    self.db.execute("DELETE FROM records WHERE kind='transactions' AND id=?",(item['id'],));removed+=1
                self.set_meta('statement-import:'+receipt['id'],{**receipt,'undone':True})
                return {'removed':removed,'kept':kept}
            return 200,self.transaction(undo)
        return None

    # Route each browser request to its Python feature.
    def dispatch(self,method,path,query=None,body=None):
        with self.lock:
            result=self.statements(method,path,body)
            if result is not None:return result
            if self.helper:
                result=self.helper.handle(method,path,query or {},body)
                if result is not None:return result
            if method=='GET' and path=='/api/health':return 200,{'ok':True,'app':'Daywell','version':'3.0','backend':'Python','pid':os.getpid()}
            if method=='GET' and path=='/api/state':return 200,self.state()
            if method=='GET' and path=='/api/backup':return 200,self.export_state(),{'Content-Disposition':'attachment; filename="daywell-backup.json"'}
            if method=='GET' and path=='/api/export.csv':
                rows=[['Date','Type','Amount','Currency','Category','Note']]+[[t['date'],t['type'],f"{t['amount']/100:.2f}",self.settings()['currency'],t['category'],t['note']] for t in sorted(self.get('transactions'),key=lambda t:t['date'])]
                return 200,'\ufeff'+'\r\n'.join(','.join(csv_cell(c) for c in row) for row in rows),{'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename="daywell-transactions.csv"'}
            if method=='POST' and path=='/api/restore':
                state=validate_state(body)
                extra=body.get('_daywell')
                metadata=payments={}
                if extra is not None:
                    object_value(extra)
                    if extra.get('version')!=1:fail('Unsupported backup version')
                    metadata=object_value(extra.get('metadata'))
                    payments=object_value(extra.get('payments'))
                    if len(metadata)>100000 or len(payments)>100000:fail('Backup history is too large')
                    for key in metadata:
                        if not isinstance(key,str) or not 1<=len(key)<=300 or key=='settings':fail('Invalid backup history')
                    for key,value in payments.items():
                        if not isinstance(key,str) or len(key)>300 or not isinstance(value,dict):fail('Invalid bill payment history')
                self.recovery_backup('before-restore')
                # Replace app records only after the entire backup passes validation.
                def restore():
                    self.db.execute('DELETE FROM records');self.db.execute('DELETE FROM payments')
                    if extra is None:self.db.execute("DELETE FROM meta WHERE key='helper_category_undo' OR key LIKE 'statement-import:%'")
                    else:self.db.execute("DELETE FROM meta WHERE key!='settings'")
                    for kind in COLLECTIONS:
                        for item in state[kind]:self.save(kind,item)
                    self.set_meta('settings',state['settings'])
                    for key,value in metadata.items():self.set_meta(key,value)
                    for key,value in payments.items():self.db.execute('INSERT INTO payments(key,body) VALUES(?,?)',(key,json_text(value)))
                self.transaction(restore);return 200,{'ok':True}
            if method=='POST' and path=='/api/settings':
                settings=validate_settings({**self.settings(),**object_value(body)});self.daily_backup();self.set_meta('settings',settings);return 200,settings
            goal_match=re.fullmatch(r'/api/goals/([^/]+)/contribute',path)
            if method=='POST' and goal_match:
                object_value(body);identifier=unquote(goal_match[1]);self.daily_backup()
                # Add to a savings goal safely without double counting retries.
                def contribute():
                    current=next((g for g in self.get('goals') if g['id']==identifier),None)
                    if current is None:fail('Goal not found. Refresh and try again.',404)
                    if not integer(body.get('amount')) or body['amount']<=0:fail('Enter an amount greater than zero in whole cents.')
                    if not integer(body.get('expectedSaved')) or body.get('expectedSaved')!=current['saved']:fail('This goal changed in another window or the contribution was already saved. Close this form and refresh before adding more.',409)
                    return self.save('goals',validate('goals',{**current,'saved':current['saved']+body['amount']}))
                return 200,self.transaction(contribute)
            bill_match=re.fullmatch(r'/api/bills/([^/]+)/pay',path)
            if method=='POST' and bill_match:
                body=object_value(body);identifier=unquote(bill_match[1]);paid=date(body.get('date'));key=identifier+'|'+paid
                old=self.db.execute('SELECT body FROM payments WHERE key=?',(key,)).fetchone()
                if old:return 200,{**json.loads(old['body']),'alreadyPaid':True}
                current=next((v for v in self.get('bills') if v['id']==identifier),None)
                if current is None:fail('Bill not found',404)
                bill=validate('bills',current)
                if bill['nextDate']!=paid:fail('Bill date changed. Refresh and try again.')
                self.daily_backup()
                # Record a bill payment once and advance its next due date.
                def pay():
                    entry=self.save('transactions',validate('transactions',{'date':paid,'type':'expense','amount':bill['amount'],'category':bill['category'],'note':'Bill: '+bill['name']}))
                    updated=self.save('bills',{**bill,'nextDate':advance_date(paid,bill['frequency'],bill['anchorDay'],bill['anchorMonth'])})
                    result={'transaction':entry,'bill':updated,'alreadyPaid':False};self.db.execute('INSERT INTO payments(key,body) VALUES(?,?)',(key,json_text(result)));return result
                return 200,self.transaction(pay)
            match=re.fullmatch(r'/api/([a-z]+)(?:/([^/]+))?',path)
            if match and match[1] in COLLECTIONS:
                kind=match[1]
                if method=='POST' and not match[2]:
                    item=validate(kind,body)
                    if kind=='bills':
                        previous=next((v for v in self.get(kind) if v['id']==item['id']),None)
                        if previous and previous['nextDate']==item['nextDate'] and previous['frequency']==item['frequency']:
                            old=validate('bills',previous);item.update(anchorDay=old['anchorDay'],anchorMonth=old['anchorMonth'])
                        else:item.update(anchorDay=int(item['nextDate'][8:]),anchorMonth=int(item['nextDate'][5:7]))
                    if kind=='checks' and not any(v['id']==item['habitId'] for v in self.get('habits')):fail('Habit not found')
                    duplicate=next((v for v in self.get(kind) if (kind=='checks' and v['date']==item['date'] and v['habitId']==item['habitId']) or (kind=='budgets' and v['month']==item['month'] and v['category']==item['category'])),None)
                    if duplicate:
                        if duplicate['id']!=item['id'] and any(v['id']==item['id'] for v in self.get(kind)):fail('An entry for this category and month already exists. Edit that entry instead.')
                        item['id']=duplicate['id']
                    self.daily_backup();return 200,self.save(kind,item)
                if method=='DELETE' and match[2]:
                    identifier=unquote(match[2]);self.daily_backup()
                    # Delete a record and clean up dependent data where needed.
                    def remove():
                        self.db.execute('DELETE FROM records WHERE kind=? AND id=?',(kind,identifier))
                        if kind=='habits':
                            for check in self.get('checks'):
                                if check['habitId']==identifier:self.db.execute("DELETE FROM records WHERE kind='checks' AND id=?",(check['id'],))
                    self.transaction(remove);return 200,{'ok':True}
            if path.startswith('/api/'):fail('Endpoint not found',404)
            return None

# Translate local HTTP requests into app actions and responses.
class DaywellHandler(BaseHTTPRequestHandler):
    server_version='Daywell/3.0'
    # Suppress the standard noisy request log in the desktop window.
    def log_message(self,*args):pass
    # Handle a read-only browser request.
    def do_GET(self):self.respond()
    # Handle a headers-only browser request.
    def do_HEAD(self):self.respond()
    # Handle a browser request that creates or changes data.
    def do_POST(self):self.respond()
    # Handle a browser request that removes data.
    def do_DELETE(self):self.respond()
    # Handle a browser request that replaces data.
    def do_PUT(self):self.respond()
    # Pass an options request through the common security checks.
    def do_OPTIONS(self):self.respond()
    # Send status, headers, and JSON or file bytes back to the browser.
    def send_value(self,status,value,headers=None):
        headers=headers or {};data=value if isinstance(value,bytes) else value.encode('utf-8') if isinstance(value,str) else json_text(value).encode('utf-8')
        self.send_response(status)
        all_headers={'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer','Permissions-Policy':'camera=(), microphone=(), geolocation=()','Content-Length':str(len(data)),**headers}
        for key,value in all_headers.items():self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)
    # Check local origin and request size before routing or serving a file.
    def respond(self):
        try:
            host=self.headers.get('Host','')
            if host not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):fail('Invalid host',403)
            parsed=urlsplit(self.path);path=parsed.path;body=None
            if self.command not in ('GET','HEAD'):
                if self.headers.get('Origin') and self.headers['Origin']!='http://'+host:fail('Cross-origin request blocked',403)
                if self.headers.get('Sec-Fetch-Site')=='cross-site':fail('Cross-site request blocked',403)
                if not re.match(r'^application/json(?:\s*;|$)',self.headers.get('Content-Type',''),re.I):fail('JSON content type required',415)
                if self.headers.get('Transfer-Encoding'):fail('Unsupported transfer encoding',400)
                try:size=int(self.headers.get('Content-Length','0'))
                except ValueError:fail('Invalid content length')
                if not 0<=size<=32*1024*1024:fail('Request too large',413)
                try:body=json.loads(self.rfile.read(size).decode('utf-8'),parse_constant=lambda _:fail('Invalid JSON'))
                except (ValueError,UnicodeDecodeError):fail('Invalid JSON')
            query={k:v[-1] for k,v in parse_qs(parsed.query,keep_blank_values=True).items()}
            if getattr(self.server.app,'auth_mode',False):
                if self.command not in ('GET','HEAD') and not self.headers.get('Origin'):
                    fail('Request origin required',403)
                result=self.server.app.dispatch(self.command,path,query,body,self.headers)
            else:
                result=self.server.app.dispatch(self.command,path,query,body)
            if result is not None:self.send_value(*result);return
            if self.command not in ('GET','HEAD'):fail('Method not allowed',405)
            root=self.server.app.public_dir
            decoded=unquote(path)
            page=self.server.app.static_page(decoded,self.headers) if getattr(self.server.app,'auth_mode',False) else None
            filename=(root/(page or ('index.html' if decoded=='/' else decoded.lstrip('/')))).resolve()
            if not filename.is_relative_to(root):fail('Forbidden',403)
            if not filename.is_file():fail('Not found',404)
            mime={'.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.html':'text/html; charset=utf-8','.svg':'image/svg+xml'}.get(filename.suffix.lower(),mimetypes.guess_type(str(filename))[0] or 'application/octet-stream')
            self.send_value(200,filename.read_bytes(),{'Content-Type':mime,'Cache-Control':'no-cache','Content-Security-Policy':CSP})
        except APIError as error:self.send_value(error.status,{'error':str(error)})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as error:
            import traceback;traceback.print_exc()
            self.send_value(500,{'error':'Something went wrong. Your saved data has been kept.'})

# Bind the app to a local-only threaded HTTP server.
class DaywellHTTPServer(ThreadingHTTPServer):
    daemon_threads=True
    # Set up local folders, open SQLite, and prepare optional helper features.
    def __init__(self,address,app):
        self.app=app;super().__init__(address,DaywellHandler)

# Build a server for the launcher or isolated tests.
def create_server(data_dir=None,port=47832,public_dir=None,helper=True,accounts=False):
    if accounts:
        directory=Path(data_dir or os.environ.get('DAYWELL_PYTHON_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local'/'share'))/'DaywellPython')
        app=AccountGateway(directory,public_dir or ROOT/'public',DaywellApp,helper=helper)
    else:
        app=DaywellApp(data_dir,public_dir,helper=helper)
    return DaywellHTTPServer(('127.0.0.1',port),app)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='Daywell local finance app')
    parser.add_argument('--port',type=int,default=int(os.environ.get('PORT','47832')))
    parser.add_argument('--data-dir',default=None)
    args=parser.parse_args()
    server=create_server(args.data_dir,args.port,accounts=os.environ.get('DAYWELL_ACCOUNTS')=='1')
    print(f'Daywell running at http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();server.app.close()
