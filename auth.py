"""Local account store for Daywell's account-enabled development mode.

The online edition will use a managed identity provider and database policies.
This module never sends personal data off the computer.
"""

import datetime as dt
import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import threading
import uuid
from pathlib import Path

from core import APIError


# Password hashes deliberately take time and memory to calculate.
SCRYPT_COST = 2 ** 15
SESSION_HOURS = 12
REMEMBER_DAYS = 30


# Normalize email addresses for unique account lookup.
def email_key(value):
    if not isinstance(value, str):
        raise APIError('Enter a valid email address.')
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise APIError('Enter a valid email address.')
    return value


# Accept long passphrases without imposing arbitrary character rules.
def check_password(value):
    if not isinstance(value, str) or not 5 <= len(value) <= 256 or not value.strip() or '\x00' in value:
        raise APIError('Use a password of at least 5 characters.')
    return value


# Convert a passphrase into an irreversible, salted memory-hard hash.
def password_hash(password, salt, pepper=None):
    material = password.encode('utf-8')
    if pepper is not None:
        material = hmac.new(pepper, material, hashlib.sha256).digest()
    return hashlib.scrypt(material, salt=salt, n=SCRYPT_COST, r=8, p=1, dklen=32, maxmem=64 * 1024 * 1024)


# Store accounts, short-lived sessions, and an audit trail outside app records.
class AccountStore:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / 'accounts.sqlite'
        self.backup_dir = self.path.parent / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash BLOB NOT NULL,
                salt BLOB NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','member')),
                created TEXT NOT NULL, privacy_accepted TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, csrf_token TEXT NOT NULL,
                expires INTEGER NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS login_failures (
                email TEXT PRIMARY KEY, count INTEGER NOT NULL, until INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS access_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, actor_id TEXT NOT NULL,
                target_id TEXT NOT NULL, action TEXT NOT NULL, at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS email_challenges (
                id TEXT PRIMARY KEY, email TEXT NOT NULL, user_id TEXT,
                password_hash BLOB, salt BLOB, code_hash TEXT NOT NULL,
                expires INTEGER NOT NULL, attempts INTEGER NOT NULL,
                sent_at INTEGER NOT NULL, privacy_accepted TEXT
            );
            CREATE TABLE IF NOT EXISTS email_sends (
                email TEXT NOT NULL, sent_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS email_sends_recent ON email_sends(email,sent_at);
        ''')
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(users)')}
        if 'hash_version' not in columns:
            self.db.execute('ALTER TABLE users ADD COLUMN hash_version INTEGER NOT NULL DEFAULT 1')
        if 'email_verified' not in columns:
            self.db.execute('ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0')
        session_columns = {row['name'] for row in self.db.execute('PRAGMA table_info(sessions)')}
        if 'admin_verified_until' not in session_columns:
            self.db.execute('ALTER TABLE sessions ADD COLUMN admin_verified_until INTEGER NOT NULL DEFAULT 0')
        try:
            self.pepper = self.load_pepper()
        except BaseException:
            self.db.close()
            raise
        # The dummy hash keeps unknown-account and wrong-password checks similar.
        self.dummy_salt = b'DaywellUnknownUserSalt2026'
        self.dummy_hash = password_hash('an unused example passphrase', self.dummy_salt, self.pepper)

    # Protect a device-specific secret with Windows DPAPI before storing it.
    def load_pepper(self):
        name = 'auth-pepper.dpapi' if os.name == 'nt' else 'auth-pepper.key'
        filename = self.path.parent / name
        if filename.exists():
            value = filename.read_bytes()
            if os.name == 'nt':
                from key_store import windows_crypt
                value = windows_crypt(value, True, b'Daywell.AccountPepper.v1')
            if len(value) != 32:
                raise RuntimeError('The Daywell account protection key is invalid.')
            return value
        protected_users = self.db.execute('SELECT count(*) FROM users WHERE hash_version>=2').fetchone()[0]
        if protected_users:
            raise RuntimeError('The Daywell account protection key is missing. Restore it before signing in.')
        value = secrets.token_bytes(32)
        if os.name == 'nt':
            from key_store import windows_crypt
            stored = windows_crypt(value, entropy=b'Daywell.AccountPepper.v1')
        else:
            stored = value
        descriptor = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(stored)
        return value

    # Count accounts so only the first local account can claim the existing data.
    def count(self):
        with self.lock:
            return self.db.execute('SELECT count(*) FROM users').fetchone()[0]

    # Create one account and assign administrator rights only at local first setup.
    def signup(self, email, password, accepted):
        key = email_key(email)
        check_password(password)
        if accepted is not True:
            raise APIError('Please review and accept the data access notice.')
        salt = secrets.token_bytes(32)
        digest = password_hash(password, salt, self.pepper)
        identifier = str(uuid.uuid4())
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.lock:
            try:
                self.db.execute('BEGIN IMMEDIATE')
                role = 'admin' if self.count() == 0 else 'member'
                self.db.execute('INSERT INTO users(id,email,password_hash,salt,role,created,privacy_accepted,hash_version) VALUES(?,?,?,?,?,?,?,2)',
                                (identifier, key, digest, salt, role, now, now))
                self.db.execute('COMMIT')
            except sqlite3.IntegrityError:
                self.db.execute('ROLLBACK')
                raise APIError('This email is already registered.', 409)
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
        self.backup()
        return {'id': identifier, 'email': key, 'role': role}

    # Issue a single-use, eight-digit code without returning it to the browser.
    def issue_email_code(self, email, delivery, user_id=None, password=None, accepted=None):
        key = email_key(email)
        if user_id is None:
            check_password(password)
            if accepted is not True:
                raise APIError('Please review and accept the data access notice.')
        if not delivery.summary()['configured']:
            raise APIError('Email verification is not ready. Ask the administrator to set up email delivery.', 503)
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        challenge = secrets.token_urlsafe(24)
        code = f'{secrets.randbelow(100000000):08d}'
        code_hash = hmac.new(self.pepper, (challenge + ':' + code).encode(), hashlib.sha256).hexdigest()
        salt = secrets.token_bytes(32) if user_id is None else None
        digest = password_hash(password, salt, self.pepper) if user_id is None else None
        with self.lock:
            self.db.execute('DELETE FROM email_sends WHERE sent_at<?', (now - 3600,))
            recent = self.db.execute('SELECT count(*),max(sent_at) FROM email_sends WHERE email=?', (key,)).fetchone()
            if recent[0] >= 3 or (recent[1] is not None and now - recent[1] < 60):
                raise APIError('Please wait before asking for another code.', 429)
            if user_id is None and self.db.execute('SELECT 1 FROM users WHERE email=?', (key,)).fetchone():
                raise APIError('This email is already registered.', 409)
            self.db.execute('INSERT INTO email_challenges VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (challenge, key, user_id, digest, salt, code_hash, now + 600, 0, now,
                             dt.datetime.now(dt.timezone.utc).isoformat() if accepted else None))
        try:
            delivery.send_code(key, code)
        except BaseException:
            with self.lock:
                self.db.execute('DELETE FROM email_challenges WHERE id=?', (challenge,))
            raise
        with self.lock:
            self.db.execute('INSERT INTO email_sends VALUES(?,?)', (key, now))
        return {'challengeId': challenge, 'expiresIn': 600, 'email': key}

    # Verify a code before creating a user or marking an existing email verified.
    def verify_email_code(self, challenge, code, user_id=None):
        if not isinstance(challenge, str) or len(challenge) > 100 or not isinstance(code, str) or not re.fullmatch(r'[0-9]{8}', code):
            raise APIError('Enter the eight-digit code from your email.')
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        with self.lock:
            row = self.db.execute('SELECT * FROM email_challenges WHERE id=?', (challenge,)).fetchone()
            if not row or row['expires'] < now or row['attempts'] >= 5 or row['user_id'] != user_id:
                raise APIError('This code expired or is no longer valid. Request a new one.', 400)
            expected = hmac.new(self.pepper, (challenge + ':' + code).encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, row['code_hash']):
                self.db.execute('UPDATE email_challenges SET attempts=attempts+1 WHERE id=?', (challenge,))
                raise APIError('That code did not match. Try again.', 400)
            try:
                self.db.execute('BEGIN IMMEDIATE')
                if user_id is None:
                    identifier = str(uuid.uuid4())
                    created = dt.datetime.now(dt.timezone.utc).isoformat()
                    self.db.execute('INSERT INTO users(id,email,password_hash,salt,role,created,privacy_accepted,hash_version,email_verified) VALUES(?,?,?,?,?,?,?,2,1)',
                                    (identifier, row['email'], row['password_hash'], row['salt'], 'member', created, row['privacy_accepted']))
                    result = {'id': identifier, 'email': row['email'], 'role': 'member'}
                else:
                    self.db.execute('UPDATE users SET email_verified=1 WHERE id=? AND email=?', (user_id, row['email']))
                    user = self.db.execute('SELECT id,email,role FROM users WHERE id=?', (user_id,)).fetchone()
                    if not user:
                        raise APIError('Account not found.', 404)
                    result = dict(user)
                self.db.execute('DELETE FROM email_challenges WHERE id=?', (challenge,))
                self.db.execute('COMMIT')
            except sqlite3.IntegrityError:
                self.db.execute('ROLLBACK')
                raise APIError('This email is already registered.', 409)
            except BaseException:
                self.db.execute('ROLLBACK')
                raise
        self.backup()
        return result

    # Apply a persistent per-account login limit before verifying a passphrase.
    def login(self, email, password):
        key = email_key(email)
        if not isinstance(password, str) or len(password) > 256:
            raise APIError('Email or passphrase is incorrect.', 401)
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        with self.lock:
            failure = self.db.execute('SELECT count,until FROM login_failures WHERE email=?', (key,)).fetchone()
            if failure and failure['count'] >= 5 and failure['until'] > now:
                raise APIError('Too many attempts. Try again in 15 minutes.', 429)
            user = self.db.execute('SELECT * FROM users WHERE email=?', (key,)).fetchone()
            version = user['hash_version'] if user else 2
            actual = password_hash(password, user['salt'] if user else self.dummy_salt, self.pepper if version >= 2 else None)
            valid = hmac.compare_digest(actual, user['password_hash'] if user else self.dummy_hash)
            if not valid:
                count = (failure['count'] if failure and failure['until'] > now else 0) + 1
                self.db.execute('INSERT INTO login_failures VALUES(?,?,?) ON CONFLICT(email) DO UPDATE SET count=excluded.count,until=excluded.until',
                                (key, count, now + 900))
                raise APIError('Email or passphrase is incorrect.', 401)
            self.db.execute('DELETE FROM login_failures WHERE email=?', (key,))
            if version == 1:
                salt = secrets.token_bytes(32)
                digest = password_hash(password, salt, self.pepper)
                self.db.execute('UPDATE users SET salt=?,password_hash=?,hash_version=2 WHERE id=?', (salt, digest, user['id']))
                self.backup()
            return {'id': user['id'], 'email': user['email'], 'role': user['role'], 'emailVerified': bool(user['email_verified'])}

    # Start a random server-side session; only its digest is saved to disk.
    def new_session(self, user, remember=False):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        seconds = REMEMBER_DAYS * 86400 if remember else SESSION_HOURS * 3600
        expires = int(dt.datetime.now(dt.timezone.utc).timestamp()) + seconds
        with self.lock:
            self.db.execute('DELETE FROM sessions WHERE expires<?', (int(dt.datetime.now(dt.timezone.utc).timestamp()),))
            self.db.execute('INSERT INTO sessions(token_hash,user_id,csrf_token,expires) VALUES(?,?,?,?)',
                            (hashlib.sha256(token.encode()).hexdigest(), user['id'], csrf, expires))
        return token, csrf, seconds

    # Look up the current account from a cookie without exposing the session ID.
    def session(self, token):
        if not isinstance(token, str) or len(token) > 100:
            return None
        key = hashlib.sha256(token.encode()).hexdigest()
        now = int(dt.datetime.now(dt.timezone.utc).timestamp())
        with self.lock:
            row = self.db.execute('SELECT users.id,users.email,users.role,users.email_verified,sessions.csrf_token,sessions.expires,sessions.admin_verified_until '
                                  'FROM sessions JOIN users ON users.id=sessions.user_id '
                                  'WHERE sessions.token_hash=? AND sessions.expires>?', (key, now)).fetchone()
        return dict(row) if row else None

    # Require a session-specific CSRF value for every account-protected write.
    def verify_csrf(self, user, value):
        if not isinstance(value, str) or not hmac.compare_digest(value, user['csrf_token']):
            raise APIError('Session check failed. Refresh the page and try again.', 403)

    # Require a fresh password for sensitive administrator actions on this session.
    def unlock_admin(self, token, user, password):
        if user['role'] != 'admin':
            raise APIError('Administrator access required.', 403)
        self.login(user['email'], password)
        until = int(dt.datetime.now(dt.timezone.utc).timestamp()) + 300
        with self.lock:
            self.db.execute('UPDATE sessions SET admin_verified_until=? WHERE token_hash=? AND user_id=?',
                            (until, hashlib.sha256(token.encode()).hexdigest(), user['id']))
        return {'validForSeconds': 300}

    # A remembered login alone must not reveal other people's records or change email delivery.
    def require_admin_unlock(self, user):
        if user['admin_verified_until'] <= int(dt.datetime.now(dt.timezone.utc).timestamp()):
            raise APIError('Confirm your password to continue in the admin dashboard.', 403)

    # Remove a session immediately when a user signs out.
    def logout(self, token):
        if token:
            with self.lock:
                self.db.execute('DELETE FROM sessions WHERE token_hash=?', (hashlib.sha256(token.encode()).hexdigest(),))

    # Show only account metadata until an administrator explicitly opens records.
    def users(self):
        with self.lock:
            return [dict(row) for row in self.db.execute('SELECT id,email,role,created,email_verified FROM users ORDER BY created')]

    # Record each administrator access to another person's financial data.
    def audit(self, actor_id, target_id, action):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        with self.lock:
            self.db.execute('INSERT INTO access_audit(actor_id,target_id,action,at) VALUES(?,?,?,?)',
                            (actor_id, target_id, action, now))
        self.backup()

    # Keep a recoverable copy of account identities and access events.
    def backup(self):
        pending = self.backup_dir / 'accounts-latest.pending.sqlite'
        latest = self.backup_dir / 'accounts-latest.sqlite'
        with self.lock:
            target = sqlite3.connect(pending)
            try:
                self.db.backup(target)
            finally:
                target.close()
            os.replace(pending, latest)
            pepper_name = 'auth-pepper.dpapi' if os.name == 'nt' else 'auth-pepper.key'
            shutil.copyfile(self.path.parent / pepper_name, self.backup_dir / pepper_name)

    # Close SQLite cleanly when the app stops.
    def close(self):
        self.db.close()
