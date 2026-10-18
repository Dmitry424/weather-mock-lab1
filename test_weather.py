"""Real loopback integration tests, including simultaneous open sessions."""
import concurrent.futures
import json
import socket
import threading
import time
import unittest
import weather_mock as w


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tcp = w.TCPServer(('127.0.0.1', 0), w.TCPHandler)
        cls.udp = w.UDPServer(('127.0.0.1', 0), 10, .1)
        for target in (cls.tcp.serve_forever, cls.udp.serve_forever, cls.udp.alerts):
            threading.Thread(target=target, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.udp.stopped.set()
        for server in (cls.tcp, cls.udp):
            server.shutdown()
            server.server_close()

    def test_four_parallel_clients(self):
        barrier = threading.Barrier(4)
        def client(city):
            with socket.create_connection(self.tcp.server_address) as s:
                s.settimeout(3)
                with s.makefile('rb') as f:
                    barrier.wait(timeout=3)
                    s.sendall(f'GET_WEATHER {city}\n'.encode())
                    reply = json.loads(f.readline())
                    barrier.wait(timeout=3)
                    s.sendall(b'EXIT\n')
                    self.assertEqual(json.loads(f.readline())['status'], 'BYE')
                    self.assertEqual(f.readline(), b'')
                    return reply
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            replies = list(pool.map(client, ['Kyiv', 'Lviv', 'Odesa', 'Dnipro']))
        self.assertEqual(len(replies), 4)
        self.assertTrue(all(r['status'] == 'OK' and r['mock'] for r in replies))

    def test_framing_errors_unicode(self):
        with socket.create_connection(self.tcp.server_address) as s, s.makefile('rb') as f:
            s.sendall(b'GET_WEA')
            s.sendall('THER Київ\nBAD\nGET_WEATHER 123\n\xff\nEXIT\n'.encode('utf-8').replace(b'\xc3\xbf', b'\xff'))
            values = [json.loads(f.readline()) for _ in range(5)]
            self.assertEqual(values[0]['city'], 'Київ')
            self.assertEqual([r.get('error') for r in values[1:4]],
                             ['UNKNOWN_COMMAND', 'INVALID_CITY', 'INVALID_UTF8'])
            self.assertEqual(values[-1]['status'], 'BYE')

    def test_long_frame(self):
        with socket.create_connection(self.tcp.server_address) as s, s.makefile('rb') as f:
            s.sendall(b'x' * (w.MAX_LINE + 1) + b'\n')
            self.assertEqual(json.loads(f.readline())['error'], 'FRAME_TOO_LONG_OR_INCOMPLETE')
            self.assertEqual(f.readline(), b'')

    def test_udp_drop_and_recovery(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.sendto(b'Packet #10', self.udp.server_address)
            start = time.monotonic()
            with self.assertRaises(socket.timeout):
                s.recvfrom(8192)
            self.assertGreaterEqual(time.monotonic()-start, .95)
            s.sendto(b'Packet #11', self.udp.server_address)
            self.assertEqual(json.loads(s.recvfrom(8192)[0])['seq'], 11)

    def test_alert_fanout(self):
        sockets = [socket.socket(socket.AF_INET, socket.SOCK_DGRAM) for _ in range(2)]
        try:
            for s in sockets:
                s.settimeout(2)
                s.sendto(b'SUBSCRIBE', self.udp.server_address)
                self.assertEqual(json.loads(s.recvfrom(8192)[0])['type'], 'SUBSCRIBED')
            for s in sockets:
                self.assertEqual(json.loads(s.recvfrom(8192)[0])['type'], 'EMERGENCY_ALERT')
                s.sendto(b'UNSUBSCRIBE', self.udp.server_address)
        finally:
            for s in sockets:
                s.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
