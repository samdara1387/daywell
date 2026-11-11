import unittest,tempfile,sqlite3,json
from pathlib import Path
from migrate import migrate,logical_snapshot
class MigrationTests(unittest.TestCase):
 def test_all_tables_and_opaque_credentials_preserved_without_overwrite(self):
  with tempfile.TemporaryDirectory() as temporary:
   old=Path(temporary)/'old';new=Path(temporary)/'new';old.mkdir()
   with sqlite3.connect(old/'daywell.sqlite') as db:
    db.executescript("CREATE TABLE records(kind TEXT,id TEXT,body TEXT);CREATE TABLE meta(key TEXT,value TEXT);CREATE TABLE payments(key TEXT,body TEXT);")
    db.execute('INSERT INTO records VALUES(?,?,?)',('transactions','one',json.dumps({'amount':1234,'category':'Food'})))
    db.execute('INSERT INTO meta VALUES(?,?)',('statement-import:receipt','{"entries":[],"undone":false}'))
    db.execute('INSERT INTO payments VALUES(?,?)',('bill|2026-01-01','{}'))
   (old/'openai-key.dpapi').write_bytes(b'opaque-ciphertext');(old/'backups').mkdir();(old/'backups'/'previous.json').write_text('{}')
   db.close()
   original=logical_snapshot(old/'daywell.sqlite')
   self.assertTrue(migrate(old,new)['verified']);self.assertEqual(original,logical_snapshot(new/'daywell.sqlite'));self.assertEqual(original,logical_snapshot(old/'daywell.sqlite'))
   self.assertEqual((new/'openai-key.dpapi').read_bytes(),b'opaque-ciphertext');self.assertTrue((new/'daywell-backups'/'previous.json').exists())
   with sqlite3.connect(new/'daywell.sqlite') as db:db.execute('INSERT INTO meta VALUES(?,?)',('new-only','kept'))
   db.close()
   self.assertFalse(migrate(old,new)['migrated']);self.assertIn(('new-only','kept'),logical_snapshot(new/'daywell.sqlite')['meta'])
if __name__=='__main__':unittest.main()
