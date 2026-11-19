"""Start Money Theory from its desktop shortcut."""

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

from migrate import migrate

# ROOT is the folder containing this file, the Python runtime, and the website.
ROOT = Path(__file__).resolve().parent
# Keep the Python app's working data separate from the original Daywell database.
LOCAL = Path(os.environ['LOCALAPPDATA'])
DATA = Path(os.environ.get('DAYWELL_PYTHON_DATA_DIR', str(LOCAL / 'DaywellPython')))
# A separate port lets original Daywell and the Python edition coexist.
PORT = int(os.environ.get('PORT', '47838'))
URL = f'http://127.0.0.1:{PORT}'


# Check whether this port already belongs to the Python edition of Daywell.
def health():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as response:
            value = json.load(response)
    except (OSError, ValueError):
        return False
    if value.get('app') not in ('Money Theory', 'Daywell') or value.get('backend') != 'Python':
        raise RuntimeError(f'Another app is using local port {PORT}.')
    if value.get('accounts') is not True:
        raise RuntimeError('An older local server is still running. Restart it to use accounts.')
    return True


# Copy data on first launch, start the local Python server, and open its window.
def main():
    if not health():
        migrate(LOCAL / 'Daywell', DATA)
        DATA.mkdir(parents=True, exist_ok=True)
        environment = {**os.environ, 'DAYWELL_PYTHON_DATA_DIR': str(DATA), 'PORT': str(PORT), 'DAYWELL_ACCOUNTS': '1'}
        executable = ROOT / 'runtime' / 'pythonw.exe'
        if not executable.is_file():
            raise RuntimeError('The bundled Python runtime is missing. Extract the full Money Theory folder.')
        with (DATA / 'server.log').open('ab') as log:
            subprocess.Popen(
                [str(executable), str(ROOT / 'server.py')],
                cwd=ROOT, env=environment, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW,
            )
        for _ in range(80):
            if health():
                break
            time.sleep(0.25)
        else:
            raise RuntimeError('Money Theory did not start. See ' + str(DATA / 'server.log'))

    if '--check' in sys.argv:
        print('Money Theory is ready at ' + URL)
        return

    # Edge's app mode makes the local website behave like a desktop window.
    candidates = [Path(os.environ.get(key, '')) / 'Microsoft/Edge/Application/msedge.exe'
                  for key in ['ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA']]
    edge = next((path for path in candidates if path.is_file()), None)
    if edge:
        profile = DATA / 'BrowserProfile'
        subprocess.Popen(
            [str(edge), '--app=' + URL, '--user-data-dir=' + str(profile),
             '--no-first-run', '--no-default-browser-check'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    else:
        import webbrowser
        webbrowser.open(URL)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        if '--check' in sys.argv:
            print(str(error))
            sys.exit(1)
        ctypes.windll.user32.MessageBoxW(0, str(error), 'Money Theory could not open', 0x10)
