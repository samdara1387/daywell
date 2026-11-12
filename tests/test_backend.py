"""Regression tests for the Python port; all fixtures use temporary directories."""
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from core import APIError, advance_date, validate, validate_state
from server import DaywellApp, create_server

class ValidationTests(unittest.TestCase):
    def test_dates_cents_and_anchor_recurrence(self):
        self.assertEqual(advance_date('2024-01-31','monthly',31,1),'2024-02-29')
        self.assertEqual(advance_date('2024-02-29','monthly',31,1),'2024-03-31')
        self.assertEqual(advance_date('2024-02-29','yearly',29,2),'2025-02-28')
        self.assertEqual(advance_date('2025-02-28','yearly',29,2),'2026-02-28')
        for amount in [True,1.1,-1,0,1000000000001]:
            with self.assertRaises(APIError):validate('transactions',{'date':'2026-10-01','type':'expense','amount':amount,'category':'Other'})
        with self.assertRaises(APIError):validate('transactions',{'date':'2026-02-29','type':'expense','amount':1,'category':'Other'})

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.app=DaywellApp(self.temp.name,helper=False)
    def tearDown(self):self.app.close();self.temp.cleanup()
    def call(self,path,body=None,method=None):
        return self.app.dispatch(method or ('GET' if body is None else 'POST'),path,{},body)
    def transaction(self,**kw):
        return {'date':'2026-10-01','type':'expense','amount':1250,'category':'Other','note':'Shop',**kw}
    def test_collections_persistence_and_settings(self):
        tx=self.call('/api/transactions',self.transaction())[1]
        habit=self.call('/api/habits',{'name':'Read','created':'2026-10-01'})[1]
        check=self.call('/api/checks',{'habitId':habit['id'],'date':'2026-10-02'})[1]
        check2=self.call('/api/checks',{'habitId':habit['id'],'date':'2026-10-02'})[1]
        self.assertEqual(check['id'],check2['id']);self.assertEqual(len(self.app.get('checks')),1)
        self.call('/api/tasks',{'title':'Finish','date':'2026-10-01','done':False})
        self.call('/api/journal',{'date':'2026-10-01','mood':4,'note':'Good day'})
        self.call('/api/settings',{'theme':'light','name':'Example'})
        state=self.app.state();self.app.close();self.app=DaywellApp(self.temp.name,helper=False)
        self.assertEqual(self.app.state(),state)
        self.call('/api/habits/'+habit['id'],method='DELETE');self.assertEqual(self.app.get('checks'),[])
        self.assertEqual(self.app.get('transactions')[0],tx)
    def test_budget_duplicate_edit_does_not_overwrite(self):
        first=self.call('/api/budgets',{'category':'Food','month':'2026-10','amount':10000})[1]
        second=self.call('/api/budgets',{'category':'Travel','month':'2026-10','amount':5000})[1]
        with self.assertRaises(APIError):self.call('/api/budgets',{**second,'category':'Food'})
        updated=self.call('/api/budgets',{'category':'Food','month':'2026-10','amount':20000})[1]
        self.assertEqual(updated['id'],first['id']);self.assertEqual(len(self.app.get('budgets')),2)
    def test_bill_pay_idempotent_and_anchors_preserved(self):
        bill=self.call('/api/bills',{'name':'Rent','nextDate':'2024-01-31','frequency':'monthly','amount':1000,'category':'Housing'})[1]
        paid=self.call('/api/bills/'+bill['id']+'/pay',{'date':'2024-01-31'})[1]
        self.assertEqual(paid['bill']['nextDate'],'2024-02-29')
        retry=self.call('/api/bills/'+bill['id']+'/pay',{'date':'2024-01-31'})[1]
        self.assertTrue(retry['alreadyPaid']);self.assertEqual(len(self.app.get('transactions')),1)
        edited=self.call('/api/bills',{**paid['bill'],'name':'Home'})[1]
        self.assertEqual(edited['anchorDay'],31)
        next_paid=self.call('/api/bills/'+bill['id']+'/pay',{'date':'2024-02-29'})[1]
        self.assertEqual(next_paid['bill']['nextDate'],'2024-03-31')
    def test_goal_contributions_retries_and_overflow(self):
        goal=self.call('/api/goals',{'name':'Trip','target':50000,'saved':100,'due':'2026-12-31'})[1]
        updated=self.call('/api/goals/'+goal['id']+'/contribute',{'amount':500,'expectedSaved':100})[1]
        self.assertEqual(updated['saved'],600)
        with self.assertRaises(APIError) as ctx:self.call('/api/goals/'+goal['id']+'/contribute',{'amount':500,'expectedSaved':100})
        self.assertEqual(ctx.exception.status,409)
        with self.assertRaises(APIError):self.call('/api/goals/'+goal['id']+'/contribute',{'amount':1000000000000,'expectedSaved':600})
        self.assertEqual(self.app.get('goals')[0]['saved'],600)
    def test_statement_validation_dedup_month_guard_and_undo(self):
        payload={'fileHash':'a'*64,'currency':'CAD','rows':[self.transaction(index=0,note='Shop A'),self.transaction(index=1,note='Shop B')]}
        with self.assertRaises(APIError):self.call('/api/import/commit',{**payload,'rows':[payload['rows'][0],{**payload['rows'][1],'amount':-1}]})
        self.assertEqual(self.app.get('transactions'),[])
        receipt=self.call('/api/import/commit',payload)[1];self.assertEqual(receipt['added'],2)
        self.assertEqual(self.call('/api/import/commit',payload)[1]['skipped'],2)
        with self.assertRaises(APIError):self.call('/api/import/commit',{**payload,'fileHash':'b'*64})
        duplicate=self.call('/api/import/commit',{**payload,'fileHash':'b'*64,'allowMonthOverlap':True})[1]
        self.assertEqual(duplicate['added'],0)
        self.assertEqual(self.call('/api/imports')[1][-1]['months'],['2026-10'])
        changed=self.app.get('transactions')[1];self.call('/api/transactions',{**changed,'category':'Education'})
        undone=self.call('/api/import/undo',{'id':receipt['id']})[1]
        self.assertEqual(undone,{'removed':1,'kept':1})
        self.assertTrue(self.call('/api/import/undo',{'id':receipt['id']})[1]['alreadyUndone'])
        self.assertEqual(len(self.app.get('transactions')),1)
        # Undo allows the original file to be imported again, with remaining records deduplicated.
        retry=self.call('/api/import/commit',payload)[1];self.assertEqual(retry['added'],1)
    def test_restore_is_atomic_and_backups_include_metadata(self):
        self.call('/api/transactions',self.transaction());original=self.app.state()
        self.app.set_meta('statement-import:test',{'id':'test','entries':[],'undone':False})
        self.app.db.execute('INSERT INTO payments(key,body) VALUES(?,?)',('test','{}'))
        invalid={**original,'transactions':[self.transaction(amount=-1)]}
        with self.assertRaises(APIError):self.call('/api/restore',invalid)
        self.assertEqual(self.app.state(),original)
        self.call('/api/restore',original)
        self.assertEqual(self.app.state(),original);self.assertEqual(self.call('/api/imports')[1],[])
        snapshots=list((Path(self.temp.name)/'backups').glob('before-restore-*.sqlite'))
        self.assertEqual(len(snapshots),1)
        db=sqlite3.connect(snapshots[0])
        try:self.assertEqual(db.execute('SELECT count(*) FROM payments').fetchone()[0],1)
        finally:db.close()
        self.assertEqual(self.app.db.execute('SELECT count(*) FROM payments').fetchone()[0],0)
    def test_downloaded_backup_restores_import_and_payment_history(self):
        imported=self.call('/api/import/commit',{'fileHash':'c'*64,'currency':'CAD','rows':[self.transaction(index=0)]})[1]
        bill=self.call('/api/bills',{'name':'Rent','nextDate':'2026-10-31','frequency':'monthly','amount':1000,'category':'Housing'})[1]
        self.call('/api/bills/'+bill['id']+'/pay',{'date':'2026-10-31'})
        self.app.set_meta('legacy-setting',{'kept':True})
        backup=self.call('/api/backup')[1]
        self.assertEqual(backup['_daywell']['version'],1)
        self.assertEqual(len(backup['_daywell']['payments']),1)
        self.assertIn('statement-import:'+imported['id'],backup['_daywell']['metadata'])
        self.assertEqual(backup['_daywell']['metadata']['legacy-setting'],{'kept':True})
        self.call('/api/restore',backup)
        self.assertEqual(self.call('/api/backup')[1],backup)
        self.assertEqual(self.call('/api/import/commit',{'fileHash':'c'*64,'currency':'CAD','rows':[self.transaction(index=0)]})[1]['added'],0)
        self.assertTrue(self.call('/api/bills/'+bill['id']+'/pay',{'date':'2026-10-31'})[1]['alreadyPaid'])
    def test_csv_injection_and_unicode(self):
        self.call('/api/transactions',self.transaction(note='=SUM(A1:A9)',category='Café'))
        csv=self.call('/api/export.csv')[1];self.assertIn('"\'=SUM(A1:A9)"',csv);self.assertIn('Café',csv)
    def test_legacy_database_rows_unchanged_on_open(self):
        self.call('/api/transactions',self.transaction());self.app.set_meta('helper_category_undo',{'items':[]})
        before=[tuple(row) for row in self.app.db.execute('SELECT * FROM records')]
        self.app.close();self.app=DaywellApp(self.temp.name,helper=False)
        self.assertEqual([tuple(row) for row in self.app.db.execute('SELECT * FROM records')],before)
        self.assertEqual(self.app.get_meta('helper_category_undo'),{'items':[]})

class HttpTests(unittest.TestCase):
    def test_http_security_static_and_api(self):
        with tempfile.TemporaryDirectory() as directory:
            http=create_server(directory,0,helper=False);thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(http.server_port)
            def request(path,method='GET',body=None,headers=None):
                data=None if body is None else json.dumps(body).encode()
                req=urllib.request.Request(base+path,data=data,method=method,headers=headers or {})
                try:
                    with urllib.request.urlopen(req) as res:return res.status,res.read(),dict(res.headers)
                except urllib.error.HTTPError as res:return res.code,res.read(),dict(res.headers)
            try:
                status,data,headers=request('/api/health');self.assertEqual(status,200);self.assertEqual(json.loads(data)['app'],'Daywell');self.assertEqual(headers['X-Frame-Options'],'DENY');self.assertEqual(headers['Referrer-Policy'],'no-referrer')
                self.assertEqual(request('/api/health',headers={'Host':'evil.example:99'})[0],403)
                self.assertEqual(request('/api/health',headers={'Host':'localhost:9999'})[0],403)
                self.assertEqual(request('/api/settings','POST',{},headers={'Content-Type':'application/json','Origin':'https://evil.example'})[0],403)
                self.assertEqual(request('/api/settings','POST',{},headers={'Content-Type':'text/plain'})[0],415)
                self.assertEqual(request('/')[0],404)
                self.assertEqual(request('/%2e%2e/server.py')[0],403)
                self.assertEqual(request('/api/not-found')[0],404)
            finally:http.shutdown();http.server_close();http.app.close();thread.join()

if __name__=='__main__':unittest.main(verbosity=2)
