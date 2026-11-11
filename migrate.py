"""Copy the complete Daywell database without altering the original."""
# This module runs only when Daywell Python has no database of its own yet.
import json, os, sqlite3, shutil
from pathlib import Path
from contextlib import closing

# Read every application table so two databases can be compared.
def logical_snapshot(path):
    with closing(sqlite3.connect(str(path))) as db:
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        return {table:sorted(db.execute('SELECT * FROM "'+table.replace('"','""')+'"').fetchall(),key=repr) for table in tables}

# Copy and verify Daywell data without changing the original database.
def migrate(source, destination):
    source,destination=Path(source),Path(destination)
    old=source/'daywell.sqlite';new=destination/'daywell.sqlite'
    destination.mkdir(parents=True,exist_ok=True)
    if new.exists():return {'migrated':False,'reason':'Existing Daywell Python data preserved'}
    if not old.exists():return {'migrated':False,'reason':'New workspace'}
    temporary=destination/'migration.sqlite'
    with closing(sqlite3.connect(str(old))) as src,closing(sqlite3.connect(str(temporary))) as dst:src.backup(dst)
    if logical_snapshot(old)!=logical_snapshot(temporary):raise RuntimeError('Migration verification failed; Daywell is unchanged.')
    for name in ['openai-key.dpapi']:
        if (source/name).exists():shutil.copy2(source/name,destination/name)
    if (source/'backups').exists():shutil.copytree(source/'backups',destination/'daywell-backups',dirs_exist_ok=True)
    temporary.replace(new)
    (destination/'migration.json').write_text(json.dumps({'source':str(source),'verified':True}),encoding='utf-8')
    return {'migrated':True,'verified':True}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--source',default=str(Path(os.environ['LOCALAPPDATA'])/'Daywell'));p.add_argument('--destination',default=str(Path(os.environ['LOCALAPPDATA'])/'DaywellPython'));a=p.parse_args()
    print(json.dumps(migrate(a.source,a.destination)))
