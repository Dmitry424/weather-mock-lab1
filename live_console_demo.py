"""Run actual concurrent TCP clients in separate Windows consoles for screenshots.

Usage: python live_console_demo.py
Each client keeps its TCP session open for 5 minutes, then sends EXIT.
Only the processes started by this script are stopped by its cleanup.
"""
import ctypes
import datetime
import json
import pathlib
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence' / 'live'


def client(city):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    ctypes.windll.kernel32.SetConsoleTitleW(f'Weather Mock TCP client - {city}')
    with (EVIDENCE / f'client_{city}.txt').open('w', encoding='utf-8') as log:
        def output(text):
            print(text, flush=True)
            log.write(text + '\n')
            log.flush()
        with socket.create_connection(('127.0.0.1', 9000), timeout=5) as sock:
            with sock.makefile('rb') as stream:
                output(f'LIVE TCP CLIENT | {city}')
                output(datetime.datetime.now().isoformat(timespec='seconds'))
                output(f'Local: {sock.getsockname()}  Server: {sock.getpeername()}')
                output('Connection stays OPEN for 5 minutes for screenshots.')
                for command in [f'GET_WEATHER {city}', 'INVALID_COMMAND']:
                    output('> ' + command)
                    sock.sendall((command + '\n').encode('utf-8'))
                    output('< ' + stream.readline().decode('utf-8').strip())
                output('STATUS: connected, waiting; no EXIT sent yet.')
                try:
                    for _ in range(30):
                        time.sleep(10)
                        # Keep the connection active before the server's 30 s idle timeout.
                        sock.sendall(f'GET_WEATHER {city}\n'.encode('utf-8'))
                        reply = json.loads(stream.readline())
                        output(f'LIVE {datetime.datetime.now():%H:%M:%S} status={reply["status"]} city={city}')
                except KeyboardInterrupt:
                    pass
                output('> EXIT')
                sock.sendall(b'EXIT\n')
                output('< ' + stream.readline().decode('utf-8').strip())
                output(f'EOF: {stream.readline()!r}')


def launch():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NEW_CONSOLE
    server = subprocess.Popen([sys.executable, '-X', 'utf8', '-u', 'weather_mock.py',
        'server', '--log', str(EVIDENCE / 'server.log')], cwd=ROOT, creationflags=flags)
    clients = []
    try:
        time.sleep(1)
        if server.poll() is not None:
            raise RuntimeError('Server did not start; check that port 9000 is available.')
        for city in ('Kyiv', 'Lviv', 'Odesa', 'Dnipro'):
            clients.append(subprocess.Popen([sys.executable, '-X', 'utf8', '-u',
                str(ROOT / 'live_console_demo.py'), '--client', city], cwd=ROOT, creationflags=flags))
        time.sleep(3)
        sessions = []
        for city in ('Kyiv', 'Lviv', 'Odesa', 'Dnipro'):
            path = EVIDENCE / f'client_{city}.txt'
            text = path.read_text(encoding='utf-8')
            if 'STATUS: connected' not in text:
                raise RuntimeError(f'{city} did not reach the connected state')
            sessions.append({'city': city, 'log': str(path.relative_to(ROOT)), 'connected': True})
        (EVIDENCE / 'sessions.json').write_text(json.dumps(sessions, indent=2), encoding='utf-8')
        print('Four LIVE console clients are connected. They exit automatically in 5 minutes.', flush=True)
        for process in clients:
            process.wait()
    finally:
        for process in clients:
            if process.poll() is None:
                process.terminate()
        if server.poll() is None:
            server.terminate()
        server.wait()


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--client':
        client(sys.argv[2])
    else:
        launch()
