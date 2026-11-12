"""Send Daywell verification emails through an administrator-owned SMTP relay."""

import json
import os
from pathlib import Path
import re
import secrets
import smtplib
import ssl
from email.message import EmailMessage

from core import APIError
from key_store import windows_crypt


# Check administrator settings before accepting a sender or server address.
def valid_config(value):
    if not isinstance(value, dict):
        raise APIError('Enter the email delivery settings.')
    host = value.get('host', '').strip() if isinstance(value.get('host'), str) else ''
    username = value.get('username', '').strip() if isinstance(value.get('username'), str) else ''
    sender = value.get('sender', '').strip() if isinstance(value.get('sender'), str) else ''
    password = value.get('password')
    port = value.get('port')
    if not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}', host) or '..' in host or host.startswith('-'):
        raise APIError('Enter a valid SMTP server name.')
    if port not in (465, 587):
        raise APIError('Use SMTP port 465 or 587.')
    if not username or len(username) > 254 or '\n' in username or '\r' in username:
        raise APIError('Enter a valid SMTP login.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', sender) or len(sender) > 254:
        raise APIError('Enter a verified sender email address.')
    if not isinstance(password, str) or not 12 <= len(password) <= 1000 or '\n' in password or '\r' in password:
        raise APIError('Enter the SMTP key supplied by your email provider.')
    return {'host': host, 'port': port, 'username': username, 'sender': sender, 'password': password}


# Keep the SMTP password outside source code in a Windows-protected local file.
class EmailDelivery:
    def __init__(self, data_dir):
        self.path = Path(data_dir) / 'smtp-settings.dpapi'

    # Return the provider settings only to Python code that sends the email.
    def load(self):
        if not self.path.is_file():
            return None
        if os.name != 'nt':
            raise RuntimeError('Local email settings require Windows encryption.')
        if self.path.stat().st_size > 10000:
            raise RuntimeError('Saved email settings are invalid.')
        raw = windows_crypt(self.path.read_bytes(), True, b'Daywell.SMTP.v1')
        data = json.loads(raw)
        if data.get('version') != 1:
            raise RuntimeError('Saved email settings are invalid.')
        return valid_config(data)

    # Show connection details to the admin without exposing the SMTP key.
    def summary(self):
        config = self.load()
        return {'configured': bool(config), **({key: config[key] for key in ('host', 'port', 'username', 'sender')} if config else {})}

    # Encrypt and atomically store a verified provider configuration.
    def save(self, value):
        config = valid_config(value)
        if os.name != 'nt':
            raise APIError('Local SMTP settings require Windows encryption.', 503)
        raw = json.dumps({'version': 1, **config}, separators=(',', ':')).encode()
        encrypted = windows_crypt(raw, entropy=b'Daywell.SMTP.v1')
        if windows_crypt(encrypted, True, b'Daywell.SMTP.v1') != raw:
            raise RuntimeError('Windows could not protect the SMTP settings.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(encrypted)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)
        return self.summary()

    # Deliver an eight-digit code without writing the code or SMTP key to logs.
    def send_code(self, address, code):
        if not re.fullmatch(r'[0-9]{8}', code):
            raise ValueError('Invalid verification code')
        self.send(address, 'Your Daywell verification code',
                  'Your Daywell verification code is ' + code + '.\n\nIt expires in 10 minutes. If you did not request it, you can ignore this email.')

    # Let the administrator verify SMTP delivery before inviting other users.
    def send_test(self, address):
        self.send(address, 'Daywell email delivery test',
                  'Your Daywell email delivery setup is working. No action is needed.')

    # Use TLS for every SMTP connection and keep failures free of credentials.
    def send(self, address, subject, text):
        config = self.load()
        if not config:
            raise APIError('Email verification is not ready. Ask the administrator to set up email delivery.', 503)
        message = EmailMessage()
        message['From'] = config['sender']
        message['To'] = address
        message['Subject'] = subject
        message.set_content(text)
        try:
            if config['port'] == 465:
                with smtplib.SMTP_SSL(config['host'], 465, timeout=15, context=ssl.create_default_context()) as server:
                    server.login(config['username'], config['password'])
                    server.send_message(message)
            else:
                with smtplib.SMTP(config['host'], 587, timeout=15) as server:
                    server.ehlo()
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                    server.login(config['username'], config['password'])
                    server.send_message(message)
        except (OSError, smtplib.SMTPException):
            raise APIError('The verification email could not be sent. Ask the administrator to check email delivery.', 502)
