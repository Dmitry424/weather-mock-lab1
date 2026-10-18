"""Lab 1, variant 16. UTF-8 JSON replies; TCP commands end with LF."""
import argparse
import hashlib
import json
import logging
import re
import socket
import socketserver
import threading
import time

MAX_LINE = 4096


def encode(value):
    return (json.dumps(value, ensure_ascii=False) + '\n').encode('utf-8')


def weather(city):
    """Stable mock values, deliberately not a real weather forecast."""
    n = int.from_bytes(hashlib.sha256(city.casefold().encode()).digest()[:4], 'big')
    return dict(status='OK', city=city, temperature_c=n % 61 - 20,
                humidity_pct=20 + n // 61 % 81, wind_m_s=round(n // 4941 % 301 / 10, 1), mock=True)


def command(text):
    if text == 'EXIT':
        return dict(status='BYE')
    if text.startswith('GET_WEATHER '):
        city = text[12:].strip()
        if city and len(city) <= 100 and all(c.isalpha() or c in " -'." for c in city):
            return weather(city)
        return dict(status='ERROR', error='INVALID_CITY')
    return dict(status='ERROR', error='UNKNOWN_COMMAND')


class TCPHandler(socketserver.StreamRequestHandler):
    def handle(self):
        logging.info('CONNECT ip=%s port=%s', *self.client_address)
        self.request.settimeout(30)
        try:
            while True:
                # TCP is a stream: readline buffers split/combined TCP segments.
                raw = self.rfile.readline(MAX_LINE + 1)
                if not raw:
                    break
                if len(raw) > MAX_LINE or not raw.endswith(b'\n'):
                    self.wfile.write(encode(dict(status='ERROR', error='FRAME_TOO_LONG_OR_INCOMPLETE')))
                    break
                try:
                    text = raw.decode('utf-8').strip()
                    answer = command(text)
                except UnicodeDecodeError:
                    text = '<invalid UTF-8>'
                    answer = dict(status='ERROR', error='INVALID_UTF8')
                logging.info('COMMAND client=%s command=%r', self.client_address, text)
                self.wfile.write(encode(answer))
                if answer['status'] == 'BYE':
                    break
        except (OSError, TimeoutError) as exc:
            logging.info('CLIENT_END %s %s', self.client_address, exc)
        finally:
            logging.info('DISCONNECT ip=%s port=%s', *self.client_address)


class TCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


class UDPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data, sock = self.request
        try:
            text = data.decode('utf-8').strip()
        except UnicodeDecodeError:
            return
        if text == 'SUBSCRIBE':
            with self.server.lock:
                self.server.listeners[self.client_address] = time.monotonic()
            sock.sendto(encode(dict(type='SUBSCRIBED')), self.client_address)
        elif text == 'UNSUBSCRIBE':
            with self.server.lock:
                self.server.listeners.pop(self.client_address, None)
        elif re.fullmatch(r'Packet #[1-9][0-9]*', text):
            seq = int(text.split('#')[1])
            if self.server.drop_every and seq % self.server.drop_every == 0:
                logging.info('UDP DROP client=%s seq=%d', self.client_address, seq)
                return
            sock.sendto(encode(dict(type='ACK', seq=seq)), self.client_address)
        else:
            sock.sendto(encode(dict(type='ERROR', error='UNKNOWN_DATAGRAM')), self.client_address)


class UDPServer(socketserver.UDPServer):
    allow_reuse_address = True

    def __init__(self, address, drop_every=10, interval=2):
        super().__init__(address, UDPHandler)
        self.drop_every = drop_every
        self.interval = interval
        self.listeners = {}
        self.lock = threading.Lock()
        self.stopped = threading.Event()

    def alerts(self):
        seq = 0
        while not self.stopped.wait(self.interval):
            seq += 1
            with self.lock:
                now = time.monotonic()
                self.listeners = {a: t for a, t in self.listeners.items() if now-t < 300}
                targets = list(self.listeners)
            for target in targets:
                try:
                    self.socket.sendto(encode(dict(type='EMERGENCY_ALERT', seq=seq,
                        message='MOCK: storm warning', mock=True)), target)
                    logging.info('ALERT seq=%d target=%s', seq, target)
                except OSError:
                    logging.exception('Alert delivery error')


def serve(args):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(threadName)s %(message)s',
                        handlers=[logging.StreamHandler(), logging.FileHandler(args.log, encoding='utf-8')])
    with TCPServer((args.host, args.tcp_port), TCPHandler) as tcp, UDPServer(
            (args.host, args.udp_port), args.drop_every, args.interval) as udp:
        threads = [threading.Thread(target=tcp.serve_forever, daemon=True),
                   threading.Thread(target=udp.serve_forever, daemon=True),
                   threading.Thread(target=udp.alerts, daemon=True)]
        for thread in threads:
            thread.start()
        logging.info('READY TCP=%s UDP=%s drop_every=%d', tcp.server_address, udp.server_address, args.drop_every)
        try:
            while True:
                time.sleep(.2)
        except KeyboardInterrupt:
            pass
        finally:
            udp.stopped.set()
            tcp.shutdown()
            udp.shutdown()


def tcp_client(args):
    # connect creates a TCP session; context manager always closes the socket.
    with socket.create_connection((args.host, args.tcp_port), timeout=5) as sock:
        stream = sock.makefile('rb')
        try:
            while True:
                try:
                    text = input('weather> ')
                except EOFError:
                    text = 'EXIT'
                sock.sendall((text + '\n').encode('utf-8'))
                raw = stream.readline(MAX_LINE + 1)
                if not raw:
                    print('Server closed connection')
                    break
                print(raw.decode('utf-8').strip())
                if json.loads(raw).get('status') == 'BYE':
                    break
        finally:
            stream.close()


def udp_probe(args):
    rows = []
    target = (socket.gethostbyname(args.host), args.udp_port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for seq in range(1, 101):
            start = time.monotonic()
            deadline = start + 1.0
            sock.sendto(f'Packet #{seq}'.encode(), target)
            received = False
            while time.monotonic() < deadline:
                sock.settimeout(max(.001, deadline-time.monotonic()))
                try:
                    raw, source = sock.recvfrom(8192)
                    value = json.loads(raw)
                    if source == target and value.get('type') == 'ACK' and value.get('seq') == seq:
                        received = True
                        break
                except socket.timeout:
                    break
                except (ValueError, UnicodeDecodeError):
                    continue
            elapsed = (time.monotonic()-start)*1000
            rows.append(dict(seq=seq, received=received, elapsed_ms=round(elapsed, 3)))
            print(f'Packet #{seq}: ' + (f'ACK RTT={elapsed:.3f} ms' if received else 'TIMEOUT (1 s)'))
    lost = sum(not row['received'] for row in rows)
    result = dict(sent=100, received=100-lost, lost=lost, loss_pct=lost, timeout_s=1, packets=rows)
    print(json.dumps({k: v for k, v in result.items() if k != 'packets'}))
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2)
    return result


def alert_client(args):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(max(5, args.interval * 3))
        target = (args.host, args.udp_port)
        sock.sendto(b'SUBSCRIBE', target)
        try:
            while True:
                raw, source = sock.recvfrom(8192)
                print(source, raw.decode().strip())
        except KeyboardInterrupt:
            pass
        finally:
            sock.sendto(b'UNSUBSCRIBE', target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['server', 'tcp', 'udp', 'alerts'])
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--tcp-port', type=int, default=9000)
    p.add_argument('--udp-port', type=int, default=9001)
    p.add_argument('--drop-every', type=int, default=10)
    p.add_argument('--interval', type=float, default=2)
    p.add_argument('--log', default='server.log')
    p.add_argument('--output')
    args = p.parse_args()
    if args.drop_every < 0 or args.interval <= 0:
        p.error('drop-every >= 0 and interval > 0 required')
    try:
        {'server': serve, 'tcp': tcp_client, 'udp': udp_probe, 'alerts': alert_client}[args.mode](args)
    except (OSError, ValueError) as exc:
        p.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
