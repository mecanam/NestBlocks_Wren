"""PC 上で接続確認の成功応答と DNS を検証: python -B tools/test_portal.py。"""
import asyncio
import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))
sys.modules['uasyncio'] = asyncio
from wren import portal, server, dns


class Writer:
    def __init__(self):
        self.data = bytearray()

    def write(self, data):
        self.data.extend(data)

    async def drain(self):
        pass

    def close(self):
        pass

    async def wait_closed(self):
        pass


class PortalTest(unittest.IsolatedAsyncioTestCase):
    async def request(self, path, method='GET', host='probe.example'):
        async def api(method, path, query, body, headers, writer, send_json):
            await send_json(writer, '200 OK', {'ok': True})

        reader = asyncio.StreamReader()
        reader.feed_data((method + ' ' + path + ' HTTP/1.1\r\nHost: ' + host + '\r\n\r\n').encode())
        reader.feed_eof()
        writer = Writer()
        await server._make_handler({'api': api, 'portal': portal.handle}, None)(reader, writer)
        return bytes(writer.data)

    async def test_probes_succeed_without_redirect(self):
        expected = {
            '/connecttest.txt': (200, b'Microsoft Connect Test'),
            '/ncsi.txt': (200, b'Microsoft NCSI'),
            '/hotspot-detect.html': (200, b'<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>'),
            '/generate_204': (204, b''),
            '/success.txt': (200, b'success'),
        }
        for path, (status, body) in expected.items():
            with self.subTest(path=path):
                response = await self.request(path + '?check=1')
                self.assertTrue(response.startswith(('HTTP/1.1 ' + str(status)).encode()))
                self.assertNotIn(b'Location:', response)
                self.assertEqual(response.split(b'\r\n\r\n', 1)[1], body)
                self.assertIn(b'Cache-Control: no-store\r\n', response)

    async def test_head_has_no_body(self):
        response = await self.request('/generate_204', 'HEAD')
        self.assertTrue(response.startswith(b'HTTP/1.1 204'))
        self.assertEqual(response.split(b'\r\n\r\n', 1)[1], b'')

    async def test_api_not_redirected(self):
        response = await self.request('/api/info')
        self.assertTrue(response.startswith(b'HTTP/1.1 200 OK'))
        self.assertNotIn(b'Location:', response)

    async def test_apple_host_unknown_path(self):
        response = await self.request('/probe-variant', host='captive.apple.com')
        self.assertTrue(response.startswith(b'HTTP/1.1 404'))
        self.assertNotIn(b'Location:', response)

    def test_editor_and_assets_not_redirected(self):
        for path in ('/', '/index.html', '/app.123456789abc.js', '/api/export', '/missing'):
            self.assertIsNone(portal.handle(path))


class DnsTest(unittest.TestCase):
    def query(self, qtype=1, edns=False):
        header = struct.pack('!6H', 123, 0x0100, 1, 0, 0, int(edns))
        question = b'\x07captive\x05apple\x03com\x00' + struct.pack('!HH', qtype, 1)
        extra = b'\x00' + struct.pack('!HHIH', 41, 1232, 0, 0) if edns else b''
        return header + question + extra

    def test_a(self):
        response = dns._build_response(self.query())
        self.assertEqual(response[6:8], b'\x00\x01')
        self.assertEqual(response[-4:], dns._IP_BYTES)

    def test_aaaa_empty_answer(self):
        response = dns._build_response(self.query(28))
        self.assertEqual(response[6:12], b'\x00' * 6)
        self.assertEqual(response[12:], self.query(28)[12:])

    def test_edns_not_copied_into_question(self):
        self.assertEqual(dns._build_response(self.query(edns=True)), dns._build_response(self.query()))

    def test_truncated_queries(self):
        query = self.query()
        for size in range(len(query)):
            self.assertIsNone(dns._build_response(query[:size]))


if __name__ == '__main__':
    unittest.main()
