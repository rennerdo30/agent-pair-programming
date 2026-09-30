"""Run browser checks against a temporary desk on an ephemeral port (never the live desk)."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent


def main():
    with tempfile.TemporaryDirectory(prefix='pairdesk-browser-test-') as data:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        if port == 8765:
            raise RuntimeError('Refusing live desk port')
        env = dict(os.environ, PAIR_DESK_DATA=data, PAIR_DESK_PORT=str(port))
        server = subprocess.Popen([sys.executable, str(ROOT / 'desk.py'), '--data', data,
                                   'serve', '--port', str(port)], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            base = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    with urllib.request.urlopen(base + '/api/health', timeout=1):
                        break
                except OSError:
                    if server.poll() is not None:
                        raise RuntimeError('Test server exited')
                    time.sleep(.1)
            else:
                raise RuntimeError('Test server did not start')
            return subprocess.call([os.environ.get('PAIR_DESK_NODE', 'node'),
                                    str(ROOT / 'scripts/ui-check.mjs'), base], env=env)
        finally:
            server.terminate()
            server.wait(timeout=10)


if __name__ == '__main__':
    sys.exit(main())
