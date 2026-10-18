"""Reproducible real socket experiment and a read-only evidence viewer."""
import concurrent.futures
import contextlib
import io
import json
import pathlib
import socket
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
import weather_mock as w

ROOT = pathlib.Path(__file__).resolve().parent
E = ROOT / 'evidence'


def experiment():
    E.mkdir(exist_ok=True)
    capture = subprocess.Popen([r'K:\wireshark\dumpcap.exe', '-i', r'\Device\NPF_Loopback',
        '-f', 'tcp port 9000 or udp port 9001', '-a', 'duration:35', '-w', str(E/'traffic.pcapng')],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    server = subprocess.Popen([sys.executable, '-X', 'utf8', str(ROOT/'weather_mock.py'), 'server',
        '--log', str(E/'server.log')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2)
        barrier = threading.Barrier(4)
        def client(city):
            lines = []
            with socket.create_connection(('127.0.0.1', 9000)) as s, s.makefile('rb') as f:
                lines.append(f'CONNECTED {s.getsockname()} -> {s.getpeername()}')
                barrier.wait(5)
                for text in [f'GET_WEATHER {city}', 'BAD_COMMAND']:
                    s.sendall((text+'\n').encode())
                    lines += ['> '+text, '< '+f.readline().decode().strip()]
                barrier.wait(5)
                time.sleep(1)
                s.sendall(b'EXIT\n')
                lines += ['> EXIT', '< '+f.readline().decode().strip(), f'EOF={f.readline()!r}']
            return '\n'.join(lines)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            sessions = list(pool.map(client, ['Kyiv', 'Lviv', 'Odesa', 'Dnipro']))
        (E/'tcp_sessions.json').write_text(json.dumps(sessions, indent=2), encoding='utf-8')
        # Exercise the interactive TCP client itself using real stdin and a real server.
        cli = subprocess.run([sys.executable, '-X', 'utf8', 'weather_mock.py', 'tcp'],
            input='GET_WEATHER Київ\nEXIT\n', capture_output=True, text=True, encoding='utf-8')
        (E/'tcp_client.txt').write_text(cli.stdout+cli.stderr, encoding='utf-8')
        alerts = []
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as a, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as b:
            for s in (a, b):
                s.settimeout(5)
                s.sendto(b'SUBSCRIBE', ('127.0.0.1', 9001))
                alerts.append(f'{s.getsockname()} '+s.recvfrom(8192)[0].decode().strip())
            for s in (a, b):
                alerts.append(f'{s.getsockname()} '+s.recvfrom(8192)[0].decode().strip())
                s.sendto(b'UNSUBSCRIBE', ('127.0.0.1', 9001))
        (E/'alerts.txt').write_text('\n'.join(alerts), encoding='utf-8')
        for drop in (10, 0):
            if drop == 0:
                server.terminate()
                server.wait()
                server = subprocess.Popen([sys.executable, '-X', 'utf8', 'weather_mock.py', 'server',
                    '--drop-every', '0', '--log', str(E/'baseline_server.log')],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(1)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                w.udp_probe(SimpleNamespace(host='127.0.0.1', udp_port=9001,
                    output=str(E/f'udp_{drop}.json')))
            (E/f'udp_{drop}.txt').write_text(output.getvalue(), encoding='utf-8')
        tests = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'unittest', '-v', 'test_weather'],
            capture_output=True, text=True, encoding='utf-8')
        (E/'tests.txt').write_text(tests.stdout+tests.stderr, encoding='utf-8')
        assert tests.returncode == 0, tests.stderr
    finally:
        server.terminate()
        server.wait()
        stdout, stderr = capture.communicate(timeout=40)
        (E/'capture.txt').write_bytes(stdout+stderr)
    print('Experiment complete. Actual evidence saved in', E)


def viewer():
    import tkinter as tk
    from tkinter import ttk
    app = tk.Tk()
    app.title('Weather Mock - REAL experiment evidence - variant 16')
    app.geometry('1450x930')
    app.configure(bg='#102138')
    tk.Label(app, text='Weather Mock | TCP / UDP | Терніков Дмитро, П-423',
             bg='#102138', fg='white', font=('Segoe UI', 18)).pack(pady=10)
    tabs = ttk.Notebook(app)
    tabs.pack(fill='both', expand=True, padx=10, pady=10)
    def panel(parent, text, row, col):
        box = tk.Text(parent, wrap='word', bg='#142b43', fg='#d5f7e8',
                      font=('Consolas', 11), padx=10, pady=10)
        box.grid(row=row, column=col, sticky='nsew', padx=4, pady=4)
        box.insert('1.0', text)
        box.configure(state='disabled')
    tcp = tk.Frame(tabs, bg='#102138')
    tabs.add(tcp, text='4 concurrent TCP clients')
    for i in range(2):
        tcp.rowconfigure(i, weight=1)
        tcp.columnconfigure(i, weight=1)
    for i, text in enumerate(json.loads((E/'tcp_sessions.json').read_text())):
        panel(tcp, f'CLIENT {i+1}\n\n'+text, i//2, i%2)
    udp = tk.Frame(tabs, bg='#102138')
    tabs.add(udp, text='UDP results + Emergency Alert')
    udp.rowconfigure(0, weight=1)
    udp.columnconfigure(0, weight=1)
    udp.columnconfigure(1, weight=1)
    text = (E/'udp_10.txt').read_text()
    lines = text.splitlines()
    selected = [line for line in lines if 'TIMEOUT' in line or 'Packet #1:' in line or 'Packet #11:' in line]
    panel(udp, 'ACTUAL UDP OUTPUT (selected lines)\n\n'+'\n'.join(selected)+'\n\n'+lines[-1], 0, 0)
    panel(udp, 'BASELINE (drop_every=0)\n'+(E/'udp_0.txt').read_text().splitlines()[-1]+
          '\n\nUDP EMERGENCY ALERT - two subscribers\n\n'+(E/'alerts.txt').read_text()+
          '\n\nINTEGRATION TESTS\n'+(E/'tests.txt').read_text(), 0, 1)
    if '--udp' in sys.argv:
        tabs.select(udp)
    app.mainloop()


if __name__ == '__main__':
    viewer() if '--viewer' in sys.argv else experiment()
