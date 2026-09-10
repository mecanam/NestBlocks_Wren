# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# server.py — uasyncio HTTP サーバー
# 設計方針 (仕様書 §6.1):
#   - ファイル数を最小に (JS 1本・CSS 1本)
#   - gzip 済みアセットを Content-Encoding: gzip で配信
#   - コンテンツハッシュ付きファイルは immutable キャッシュ
#   - index.html は no-cache
#   - 1~2 KB チャンクでストリーミング送信

import uasyncio
import os
import gc
from . import portal as _portal

_CHUNK = 1536   # 送信チャンクサイズ (bytes)

# ── MIME タイプ ────────────────────────────────────────────────
_MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js':   'application/javascript',
    '.css':  'text/css',
    '.json': 'application/json',
    '.ico':  'image/x-icon',
    '.png':  'image/png',
}

# ── レスポンスヘルパー ─────────────────────────────────────────
async def _send_headers(writer, status, headers):
    lines = [f'HTTP/1.1 {status}\r\n']
    for k, v in headers.items():
        lines.append(f'{k}: {v}\r\n')
    lines.append('\r\n')
    writer.write(''.join(lines).encode())
    await writer.drain()

async def _send_json(writer, status, obj):
    import json
    body = json.dumps(obj).encode()
    await _send_headers(writer, status, {
        'Content-Type': 'application/json',
        'Content-Length': str(len(body)),
        'Access-Control-Allow-Origin': '*',
        'Connection': 'close',
    })
    writer.write(body)
    await writer.drain()

async def _send_file(writer, path, gzipped=False, immutable=False):
    """LittleFS 上のファイルをストリーミング送信する。"""
    try:
        stat = os.stat(path)
        size = stat[6]
    except OSError:
        await _send_json(writer, '404 Not Found', {'error': 'not found'})
        return

    ext = '.' + path.rsplit('.', 1)[-1] if '.' in path else ''
    if gzipped and path.endswith('.gz'):
        # 拡張子 .gz の前を取得して MIME を判定
        real_ext = '.' + path[:-3].rsplit('.', 1)[-1]
        mime = _MIME.get(real_ext, 'application/octet-stream')
    else:
        mime = _MIME.get(ext, 'application/octet-stream')

    cache = ('public, max-age=31536000, immutable'
             if immutable else 'no-cache, no-store')

    headers = {
        'Content-Type':  mime,
        'Content-Length': str(size),
        'Cache-Control': cache,
        'Connection':    'close',
    }
    if gzipped:
        headers['Content-Encoding'] = 'gzip'

    await _send_headers(writer, '200 OK', headers)

    with open(path, 'rb') as f:
        while True:
            chunk = f.read(_CHUNK)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()
            gc.collect()

# ── リクエストパーサー ─────────────────────────────────────────
async def _parse_request(reader):
    """1 リクエスト分のヘッダーとボディを読む。"""
    # 1 行目: メソッド・パス・バージョン
    line = await reader.readline()
    if not line:
        return None, None, None, None
    parts = line.decode().strip().split(' ')
    if len(parts) < 2:
        return None, None, None, None
    method = parts[0].upper()
    raw_path = parts[1]
    # クエリ文字列を分離
    path, _, query = raw_path.partition('?')

    # ヘッダーを読む
    headers = {}
    while True:
        hline = await reader.readline()
        if hline in (b'\r\n', b'\n', b''):
            break
        if b':' in hline:
            k, _, v = hline.decode().partition(':')
            headers[k.strip().lower()] = v.strip()

    # ボディ (POST)
    body = b''
    if method in ('POST', 'PUT', 'PATCH'):
        length = int(headers.get('content-length', 0))
        if length > 0:
            body = await reader.readexactly(length)

    return method, path, query, body, headers

# ── メインハンドラ ─────────────────────────────────────────────
def _make_handler(routes, led_task_ref):
    api_handle    = routes['api']
    portal_handle = routes['portal']

    async def handler(reader, writer):
        try:
            parsed = await _parse_request(reader)
            if parsed[0] is None:
                return

            method, path, query, body, req_headers = parsed

            # ── キャプティブポータル ──────────────────────────
            portal_resp = portal_handle(path) if method in ('GET', 'HEAD') else None
            if portal_resp:
                status, ct, body_bytes = portal_resp
                portal_headers = {
                    'Content-Type':   ct,
                    'Content-Length': str(len(body_bytes)),
                    'Cache-Control':  'no-store',
                    'Connection':     'close',
                }
                reason = 'No Content' if status == 204 else 'OK'
                await _send_headers(writer, f'{status} {reason}', portal_headers)
                if body_bytes and method != 'HEAD':
                    writer.write(body_bytes)
                    await writer.drain()
                return

            # ── API ──────────────────────────────────────────
            if path.startswith('/api/'):
                await api_handle(method, path, query, body, req_headers,
                                 writer, _send_json)
                return

            # ── 静的ファイル ─────────────────────────────────
            if path in ('/', '/index.html'):
                # index.html は no-cache で提供
                html_path = '/www/index.html'
                if _file_exists(html_path):
                    await _send_file(writer, html_path, immutable=False)
                else:
                    await _send_json(writer, '503 Service Unavailable',
                                     {'error': 'build not deployed'})
                return

            # ハッシュ付き JS/CSS (immutable)
            fname = path.lstrip('/')
            gz_path = f'/www/{fname}.gz'
            if _file_exists(gz_path):
                await _send_file(writer, gz_path, gzipped=True, immutable=True)
                return

            plain_path = f'/www/{fname}'
            if _file_exists(plain_path):
                await _send_file(writer, plain_path, immutable=True)
                return

            await _send_json(writer, '404 Not Found', {'error': path})

        except Exception as e:
            print('[server] handler error:', e)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    return handler

def _file_exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

# ── 公開 API ──────────────────────────────────────────────────
async def create(host, port, routes, led_task=None):
    handler = _make_handler(routes, led_task)
    srv = await uasyncio.start_server(handler, host, port)
    print(f'[HTTP] 起動 (:{port})')
    return srv
