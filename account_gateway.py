"""Account-aware routing for the local Daywell development server."""

from http.cookies import SimpleCookie
from pathlib import Path
import re
import threading

from auth import AccountStore
from core import APIError, object_value
from mail_service import EmailDelivery


# Give each signed-in person a separate Daywell database and backup folder.
class AccountGateway:
    auth_mode = True

    def __init__(self, data_dir, public_dir, app_factory, helper=True):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir = Path(public_dir).resolve()
        self.accounts = AccountStore(self.data_dir)
        self.email = EmailDelivery(self.data_dir)
        self.app_factory = app_factory
        self.helper = helper
        self.apps = {}
        self.lock = threading.RLock()

    # Read only Daywell's session cookie; ignore unrelated browser cookies.
    def token(self, headers):
        try:
            cookies = SimpleCookie(headers.get('Cookie', ''))
            return cookies['daywell_session'].value if 'daywell_session' in cookies else None
        except Exception:
            return None

    # Prepare a cookie that scripts cannot read and other sites cannot send.
    def cookie_header(self, token, seconds=None):
        value = f'daywell_session={token}; Path=/; HttpOnly; SameSite=Strict'
        if seconds is not None:
            value += f'; Max-Age={seconds}'
        return value

    # The first local account owns the pre-existing Daywell database.
    def app_for(self, user):
        with self.lock:
            identifier = user['id']
            if identifier not in self.apps:
                directory = self.data_dir if user['role'] == 'admin' else self.data_dir / 'accounts' / identifier
                self.apps[identifier] = self.app_factory(directory, self.public_dir, helper=self.helper)
            return self.apps[identifier]

    # Route login, account data, and audited administrator reads.
    def dispatch(self, method, path, query, body, headers):
        if not path.startswith('/api/'):
            return None
        if method == 'GET' and path == '/api/health':
            return 200, {'ok': True, 'app': 'Daywell', 'version': '3.1', 'backend': 'Python', 'accounts': True}
        token = self.token(headers)
        user = self.accounts.session(token) if token else None
        if method == 'POST' and path in ('/api/auth/signup', '/api/auth/login'):
            body = object_value(body)
            if path.endswith('signup'):
                if self.accounts.count() != 0:
                    raise APIError('Enter the code sent to your email to create an account.', 409)
                created = self.accounts.signup(body.get('email'), body.get('password'), body.get('privacyAccepted'))
                account = created
            else:
                account = self.accounts.login(body.get('email'), body.get('password'))
            remember = body.get('remember') is True
            new_token, csrf, seconds = self.accounts.new_session(account, remember)
            return 200, {'user': account, 'csrf': csrf}, {'Set-Cookie': self.cookie_header(new_token, seconds if remember else None)}
        if method == 'POST' and path == '/api/auth/signup/start':
            if self.accounts.count() == 0:
                raise APIError('Set up the first local account before inviting others.', 409)
            body = object_value(body)
            return 200, self.accounts.issue_email_code(body.get('email'), self.email, password=body.get('password'), accepted=body.get('privacyAccepted'))
        if method == 'POST' and path == '/api/auth/signup/verify':
            body = object_value(body)
            account = self.accounts.verify_email_code(body.get('challengeId'), body.get('code'))
            remember = body.get('remember') is True
            new_token, csrf, seconds = self.accounts.new_session(account, remember)
            return 200, {'user': account, 'csrf': csrf}, {'Set-Cookie': self.cookie_header(new_token, seconds if remember else None)}
        if method == 'GET' and path == '/api/auth/setup':
            return 200, {'firstAccount': self.accounts.count() == 0, 'emailConfigured': self.email.summary()['configured']}
        if method == 'GET' and path == '/api/auth/session':
            if not user:
                raise APIError('Please sign in.', 401)
            return 200, {'user': {k: user[k] for k in ('id', 'email', 'role')}, 'emailVerified': bool(user['email_verified']), 'csrf': user['csrf_token']}
        if not user:
            raise APIError('Please sign in.', 401)
        if method not in ('GET', 'HEAD'):
            self.accounts.verify_csrf(user, headers.get('X-CSRF-Token'))
        if method == 'POST' and path == '/api/auth/logout':
            self.accounts.logout(token)
            return 200, {'ok': True}, {'Set-Cookie': self.cookie_header('', 0)}
        if method == 'POST' and path == '/api/auth/email/start':
            return 200, self.accounts.issue_email_code(user['email'], self.email, user_id=user['id'])
        if method == 'POST' and path == '/api/auth/email/verify':
            body = object_value(body)
            self.accounts.verify_email_code(body.get('challengeId'), body.get('code'), user_id=user['id'])
            return 200, {'emailVerified': True}
        if path.startswith('/api/auth/'):
            raise APIError('Endpoint not found', 404)
        if path.startswith('/api/admin/'):
            if user['role'] != 'admin':
                raise APIError('Administrator access required.', 403)
            if method == 'POST' and path == '/api/admin/unlock':
                return 200, self.accounts.unlock_admin(token, user, object_value(body).get('password'))
            if method == 'GET' and path == '/api/admin/summary':
                return 200, {'users': self.accounts.users()}
            if method == 'GET' and path == '/api/admin/email/config':
                return 200, self.email.summary()
            if method == 'POST' and path == '/api/admin/email/config':
                self.accounts.require_admin_unlock(user)
                return 200, self.email.save(object_value(body))
            if method == 'POST' and path == '/api/admin/email/test':
                self.accounts.require_admin_unlock(user)
                self.email.send_test(user['email'])
                return 200, {'sentTo': user['email']}
            match = re.fullmatch(r'/api/admin/users/([0-9a-f-]+)/state', path)
            if method == 'GET' and match:
                self.accounts.require_admin_unlock(user)
                target = next((u for u in self.accounts.users() if u['id'] == match[1]), None)
                if not target:
                    raise APIError('Account not found.', 404)
                self.accounts.audit(user['id'], target['id'], 'view-state')
                return 200, {'user': target, 'state': self.app_for(target).state()}
            raise APIError('Endpoint not found', 404)
        return self.app_for(user).dispatch(method, path, query, body)

    # Permit the administrator dashboard only to a signed-in administrator.
    def static_page(self, path, headers):
        user = self.accounts.session(self.token(headers))
        if path in ('/', '/index.html') and not user:
            return 'auth.html'
        if path in ('/admin', '/admin.html'):
            if not user or user['role'] != 'admin':
                raise APIError('Administrator access required.', 403)
            return 'admin.html'
        return None

    # Close all personal databases and the account store.
    def close(self):
        for app in self.apps.values():
            app.close()
        self.accounts.close()
