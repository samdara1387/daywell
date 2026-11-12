"""Account, session, and tenant-isolation checks using fictional records."""

import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from auth import AccountStore, password_hash
from core import APIError
from server import DaywellApp, create_server


class AccountStoreTests(unittest.TestCase):
    def test_existing_session_table_migrates_without_losing_accounts(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, 'accounts.sqlite')
            db = sqlite3.connect(path)
            try:
                db.execute('CREATE TABLE sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL,csrf_token TEXT NOT NULL,expires INTEGER NOT NULL)')
            finally:
                db.close()
            store = AccountStore(directory)
            try:
                columns = {row['name'] for row in store.db.execute('PRAGMA table_info(sessions)')}
                self.assertIn('admin_verified_until', columns)
                account = store.signup('owner@example.com', 'abcde', True)
                token, _, _ = store.new_session(account)
                self.assertEqual(store.session(token)['admin_verified_until'], 0)
            finally:
                store.close()

    def test_failed_delivery_and_exhausted_codes_cannot_create_accounts(self):
        class FakeEmail:
            fail = True
            code = None
            def summary(self): return {'configured': True}
            def send_code(self, address, code):
                if self.fail: raise APIError('Email delivery failed.', 502)
                self.code = code
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(directory)
            try:
                store.signup('owner@example.com', 'abcde', True)
                email = FakeEmail()
                with self.assertRaises(APIError):
                    store.issue_email_code('new@example.com', email, password='abcde', accepted=True)
                self.assertEqual(store.count(), 1)
                self.assertEqual(store.db.execute('SELECT count(*) FROM email_challenges').fetchone()[0], 0)
                email.fail = False
                challenge = store.issue_email_code('new@example.com', email, password='abcde', accepted=True)['challengeId']
                wrong = '00000000' if email.code != '00000000' else '11111111'
                for _ in range(5):
                    with self.assertRaises(APIError): store.verify_email_code(challenge, wrong)
                with self.assertRaises(APIError): store.verify_email_code(challenge, email.code)
                self.assertEqual(store.count(), 1)
            finally:
                store.close()

    def test_email_code_is_single_use_and_marks_existing_account_verified(self):
        class FakeEmail:
            code = None
            def summary(self): return {'configured': True}
            def send_code(self, address, code): self.code = code
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(directory)
            try:
                admin = store.signup('owner@example.com', 'abcde', True)
                delivery = FakeEmail()
                issued = store.issue_email_code(admin['email'], delivery, user_id=admin['id'])
                with self.assertRaises(APIError):
                    store.verify_email_code(issued['challengeId'], '12345678', user_id=admin['id'])
                result = store.verify_email_code(issued['challengeId'], delivery.code, user_id=admin['id'])
                self.assertEqual(result['id'], admin['id'])
                self.assertEqual(store.users()[0]['email_verified'], 1)
                with self.assertRaises(APIError):
                    store.verify_email_code(issued['challengeId'], delivery.code, user_id=admin['id'])
                with self.assertRaises(APIError) as limited:
                    store.issue_email_code(admin['email'], delivery, user_id=admin['id'])
                self.assertEqual(limited.exception.status, 429)
            finally:
                store.close()

    def test_device_secret_is_required_for_new_password_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(directory)
            try:
                account = store.signup('owner@example.com', 'abcde', True)
                row = store.db.execute('SELECT salt,password_hash,hash_version FROM users WHERE id=?', (account['id'],)).fetchone()
                self.assertEqual(row['hash_version'], 2)
                self.assertNotEqual(row['password_hash'], password_hash('abcde', row['salt']))
            finally:
                store.close()
            secret = store.path.parent / ('auth-pepper.dpapi' if os.name == 'nt' else 'auth-pepper.key')
            secret.unlink()
            with self.assertRaises(RuntimeError):
                AccountStore(directory)

    def test_password_session_and_login_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            store = AccountStore(directory)
            try:
                admin = store.signup('Owner@Example.com', 'a long and private passphrase', True)
                self.assertEqual(admin['role'], 'admin')
                member = store.signup('Member@Example.com', 'another long private passphrase', True)
                self.assertEqual(member['role'], 'member')
                short = store.signup('five@example.com', 'abcde', True)
                self.assertEqual(store.login('five@example.com', 'abcde')['id'], short['id'])
                with self.assertRaises(APIError):
                    store.signup('no@example.com', 'four', True)
                self.assertTrue((store.backup_dir / ('auth-pepper.dpapi' if os.name == 'nt' else 'auth-pepper.key')).is_file())
                for _ in range(5):
                    with self.assertRaises(APIError):
                        store.login('member@example.com', 'a wrong passphrase')
                with self.assertRaises(APIError) as blocked:
                    store.login('member@example.com', 'another long private passphrase')
                self.assertEqual(blocked.exception.status, 429)
                token, csrf, _ = store.new_session(admin, True)
                session = store.session(token)
                self.assertEqual(session['id'], admin['id'])
                store.verify_csrf(session, csrf)
                with self.assertRaises(APIError):
                    store.verify_csrf(session, 'wrong')
                store.logout(token)
                self.assertIsNone(store.session(token))
            finally:
                store.close()


class AccountHttpTests(unittest.TestCase):
    def test_first_account_keeps_existing_local_records(self):
        with tempfile.TemporaryDirectory() as directory:
            old = DaywellApp(directory, helper=False)
            try:
                old.dispatch('POST', '/api/transactions', {}, {'date': '2026-11-10', 'type': 'expense', 'amount': 450, 'category': 'Food', 'note': 'Existing lunch'})
            finally:
                old.close()
            server = create_server(directory, 0, helper=False, accounts=True)
            try:
                owner = server.app.accounts.signup('owner@example.com', 'a long owner passphrase', True)
                self.assertEqual(server.app.app_for(owner).state()['transactions'][0]['note'], 'Existing lunch')
                member = server.app.accounts.signup('member@example.com', 'a long member passphrase', True)
                self.assertEqual(server.app.app_for(member).state()['transactions'], [])
            finally:
                server.server_close()
                server.app.close()

    def test_login_gate_tenant_isolation_admin_and_csrf(self):
        with tempfile.TemporaryDirectory() as directory:
            server = create_server(directory, 0, helper=False, accounts=True)
            class FakeEmail:
                code = None
                def summary(self): return {'configured': True}
                def send_code(self, address, code): self.code = code
            email = FakeEmail()
            server.app.email = email
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.server_port}'

            def call(path, method='GET', data=None, cookie=None, csrf=None):
                headers = {}
                if method != 'GET':
                    headers.update({'Origin': base, 'Content-Type': 'application/json'})
                if cookie:
                    headers['Cookie'] = cookie
                if csrf:
                    headers['X-CSRF-Token'] = csrf
                body = json.dumps(data or {}).encode() if method != 'GET' else None
                request = urllib.request.Request(base + path, data=body, headers=headers, method=method)
                try:
                    response = urllib.request.urlopen(request)
                except urllib.error.HTTPError as error:
                    response = error
                with response:
                    content = response.read()
                    return response.status, json.loads(content) if path.startswith('/api/') else content, response.headers

            try:
                self.assertEqual(call('/api/state')[0], 401)
                self.assertIn(b'Create account', call('/')[1])
                owner = call('/api/auth/signup', 'POST', {'email': 'owner@example.com', 'password': 'a long owner passphrase', 'privacyAccepted': True})
                self.assertEqual(owner[0], 200)
                self.assertIn('HttpOnly', owner[2]['Set-Cookie'])
                admin_cookie = owner[2]['Set-Cookie'].split(';', 1)[0]
                admin_csrf = owner[1]['csrf']
                self.assertEqual(call('/api/admin/summary', cookie=admin_cookie)[0], 200)
                signup = {'email': 'member@example.com', 'password': 'a long member passphrase', 'privacyAccepted': True}
                self.assertEqual(call('/api/auth/signup', 'POST', signup)[0], 409)
                pending = call('/api/auth/signup/start', 'POST', signup)
                self.assertEqual(pending[0], 200)
                self.assertEqual(call('/api/auth/signup/verify', 'POST', {'challengeId': pending[1]['challengeId'], 'code': '00000000'})[0], 400)
                member = call('/api/auth/signup/verify', 'POST', {'challengeId': pending[1]['challengeId'], 'code': email.code})
                self.assertEqual(member[0], 200)
                self.assertEqual(server.app.accounts.users()[1]['email_verified'], 1)
                member_cookie = member[2]['Set-Cookie'].split(';', 1)[0]
                member_csrf = member[1]['csrf']
                self.assertEqual(call('/api/admin/summary', cookie=member_cookie)[0], 403)
                item = {'date': '2026-11-10', 'type': 'expense', 'amount': 1200, 'category': 'Food', 'note': 'Private lunch'}
                self.assertEqual(call('/api/transactions', 'POST', item, member_cookie)[0], 403)
                self.assertEqual(call('/api/transactions', 'POST', item, member_cookie, member_csrf)[0], 200)
                self.assertEqual(call('/api/state', cookie=admin_cookie)[1]['transactions'], [])
                member_id = member[1]['user']['id']
                self.assertEqual(call(f'/api/admin/users/{member_id}/state', cookie=admin_cookie)[0], 403)
                self.assertEqual(call('/api/admin/email/config', 'POST', {'host': 'smtp.example.com'}, admin_cookie, admin_csrf)[0], 403)
                self.assertEqual(call('/api/admin/unlock', 'POST', {'password': 'a long owner passphrase'}, admin_cookie)[0], 403)
                self.assertEqual(call('/api/admin/unlock', 'POST', {'password': 'wrong password'}, admin_cookie, admin_csrf)[0], 401)
                self.assertEqual(call('/api/admin/unlock', 'POST', {'password': 'a long owner passphrase'}, admin_cookie, admin_csrf)[0], 200)
                detail = call(f'/api/admin/users/{member_id}/state', cookie=admin_cookie)
                self.assertEqual(detail[0], 200)
                self.assertEqual(detail[1]['state']['transactions'][0]['note'], 'Private lunch')
                self.assertEqual(server.app.accounts.db.execute('SELECT count(*) FROM access_audit').fetchone()[0], 1)
                server.app.accounts.db.execute('UPDATE sessions SET admin_verified_until=0')
                self.assertEqual(call(f'/api/admin/users/{member_id}/state', cookie=admin_cookie)[0], 403)
                self.assertEqual(call('/api/auth/logout', 'POST', {}, admin_cookie, admin_csrf)[0], 200)
                self.assertEqual(call('/api/admin/summary', cookie=admin_cookie)[0], 401)
            finally:
                server.shutdown()
                server.server_close()
                server.app.close()
                thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
