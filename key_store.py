"""User-scoped Windows DPAPI storage, compatible with Daywell key files."""
from pathlib import Path
import ctypes
import json
import os
import re
import uuid

# Protect or unlock a key with Windows encryption for this user account.
def windows_crypt(value, decrypt=False, entropy=b'Daywell.OpenAI.v1'):
    if os.name != 'nt':
        raise ValueError('Windows encryption is unavailable.')
    from ctypes import wintypes
    # Describe the byte structure required by the Windows encryption API.
    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]
    # Turn Python bytes into the structure expected by Windows.
    def blob(data):
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        return Blob(len(data), buffer), buffer
    incoming, keep = blob(value)
    entropy, keep_entropy = blob(entropy)
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(incoming), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
        raise ValueError('Windows could not protect or unlock the saved key.')
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        ctypes.memset(output.pbData, 0, output.cbData)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(output.pbData)

# Keep an optional online key outside the database.
class KeyStore:
    available = os.name == 'nt'
    # Choose the encrypted key file in the local data folder.
    def __init__(self, data_dir):
        self.filename = Path(data_dir) / 'openai-key.dpapi'
    # Decrypt and validate a previously saved key.
    def load(self):
        try:
            encrypted = self.filename.read_bytes()
        except FileNotFoundError:
            return None
        if len(encrypted) > 32768:
            raise ValueError('Invalid saved key.')
        value = json.loads(windows_crypt(encrypted, True))
        key, model = value.get('apiKey'), value.get('model')
        if value.get('version') != 1 or not isinstance(key, str) or not 20 <= len(key) <= 1000 or re.search(r'\s', key) or not isinstance(model, str) or not re.fullmatch(r'[a-zA-Z0-9._:-]{1,100}', model):
            raise ValueError('Invalid saved key.')
        return value
    # Encrypt a key, verify it, then replace the file atomically.
    def save(self, value):
        clear = json.dumps({'version': 1, 'apiKey': value['apiKey'], 'model': value['model']}, separators=(',', ':')).encode()
        encrypted = windows_crypt(clear)
        if windows_crypt(encrypted, True) != clear:
            raise ValueError('Windows encryption verification failed.')
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.filename.with_name(self.filename.name + '.' + str(uuid.uuid4()) + '.tmp')
        try:
            with open(temporary, 'xb') as output:
                output.write(encrypted)
            os.replace(temporary, self.filename)
        finally:
            temporary.unlink(missing_ok=True)
    # Remove the saved encrypted key when the user requests it.
    def forget(self):
        self.filename.unlink(missing_ok=True)
