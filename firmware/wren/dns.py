# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# dns.py — 簡易 DNS サーバー (UDP 53)
# 任意のドメインに対して 192.168.4.1 を返す。
# キャプティブポータル検知 + wren.local 相当のアクセスを実現する。

import uasyncio
import socket
import struct
from . import config

_IP_BYTES = bytes(int(x) for x in config.IP.split('.'))

def _parse_name(data, offset):
    """DNS クエリからドメイン名を取り出す。"""
    labels = []
    while True:
        if offset >= len(data):
            raise ValueError('truncated DNS name')
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 or offset + 1 + length > len(data):
            raise ValueError('unsupported or truncated DNS name')
        offset += 1
        labels.append(data[offset:offset + length].decode('ascii', 'ignore'))
        offset += length
    return '.'.join(labels), offset

def _build_response(query):
    """A のみ IPv4 を返し、AAAA 等には正常な空回答を返す。"""
    if len(query) < 12 or query[2] & 0xF8 or query[4:6] != b'\x00\x01':
        return None
    try:
        _, end = _parse_name(query, 12)
    except ValueError:
        return None
    if end + 4 > len(query):
        return None
    qtype, qclass = struct.unpack('!HH', query[end:end + 4])
    has_answer = qtype == 1 and qclass == 1
    tid    = query[:2]
    flags  = bytes((0x84 | (query[2] & 1), 0))  # QR, AA, RD を引き継ぐ
    qdcount = query[4:6]
    ancount = b'\x00\x01' if has_answer else b'\x00\x00'
    nscount = b'\x00\x00'
    arcount = b'\x00\x00'

    # Questions セクションをそのままコピー
    # EDNS の追加レコードを Question としてコピーしない。
    questions = query[12:end + 4]

    # Answers セクション (ポインタで質問名を参照)
    answer = (
        b'\xc0\x0c'         # name: pointer to offset 12 (question name)
        b'\x00\x01'         # type: A
        b'\x00\x01'         # class: IN
        b'\x00\x00\x00\x1e' # TTL: 30 秒
        b'\x00\x04'         # rdlength: 4 bytes
        + _IP_BYTES
    )

    return (
        tid + flags + qdcount + ancount + nscount + arcount
        + questions + (answer if has_answer else b'')
    )

async def serve():
    """UDP 53 番で DNS リクエストを待ち受ける。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', 53))
    sock.setblocking(False)

    print('[DNS] 起動 (UDP 53)')

    while True:
        try:
            data, addr = sock.recvfrom(512)
            if len(data) < 12:
                continue
            resp = _build_response(data)
            if resp is not None:
                sock.sendto(resp, addr)
        except OSError:
            await uasyncio.sleep_ms(10)
        except Exception as e:
            print('[DNS] エラー:', e)
            await uasyncio.sleep_ms(100)
