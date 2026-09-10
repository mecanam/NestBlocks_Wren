# Phase 0 / P3 — HTTP 転送速度ベンチ (Pico W 側)
# Pico W の main.py として書き込み、AP に接続して
# ブラウザ or p3_client.py から http://192.168.4.1/bench にアクセスする
#
# 判定基準: ブラウザで 20 秒以内に表示完了
# 推奨目標: 10 秒以内

import network
import uasyncio
import utime

# ── 設定 ──────────────────────────────────────
SSID     = 'Wren-BENCH'
PASSWORD = 'bench1234'
IP       = '192.168.4.1'
PORT     = 80

# 356 KB のダミーペイロード (目標サイズを模擬)
PAYLOAD_SIZE = 356 * 1024
# ──────────────────────────────────────────────

def setup_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(ssid=SSID, password=PASSWORD, channel=1,
              security=network.AUTH_WPA2_PSK)
    ap.ifconfig((IP, '255.255.255.0', IP, IP))
    while not ap.active():
        utime.sleep_ms(100)
    print(f'AP 起動: ssid={SSID}  ip={IP}')

async def handle(reader, writer):
    try:
        req = await reader.read(512)
        first = req.split(b'\r\n')[0].decode()
        path = first.split(' ')[1] if len(first.split(' ')) > 1 else '/'

        if path == '/bench':
            # 転送開始時刻
            t0 = utime.ticks_ms()
            sent = 0
            chunk = b'X' * 1024   # 1 KB チャンク

            header = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: application/octet-stream\r\n'
                f'Content-Length: {PAYLOAD_SIZE}\r\n'
                'Cache-Control: no-cache\r\n'
                'Connection: close\r\n\r\n'
            )
            writer.write(header.encode())
            await writer.drain()

            while sent < PAYLOAD_SIZE:
                remain = PAYLOAD_SIZE - sent
                writer.write(chunk if remain >= 1024 else b'X' * remain)
                await writer.drain()
                sent += min(1024, remain)

            elapsed = utime.ticks_diff(utime.ticks_ms(), t0)
            rate = PAYLOAD_SIZE / elapsed  # KB/s
            print(f'[BENCH] {PAYLOAD_SIZE//1024} KB を {elapsed} ms で送信'
                  f'  ({rate:.1f} KB/s)  → {"PASS" if elapsed < 20000 else "FAIL"}')

        elif path == '/result':
            # REPL から確認するためのシンプルな結果ページ
            body = (
                '<html><body>'
                '<h1>P3 ベンチ完了</h1>'
                '<p>REPL で転送時間を確認してください</p>'
                '</body></html>'
            )
            resp = (
                'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n'
                f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}'
            )
            writer.write(resp.encode())
            await writer.drain()

        else:
            # ルート: 案内ページ
            body = (
                '<html><body>'
                '<h1>P3 Bench Server</h1>'
                '<p><a href="/bench">▶ 356 KB 転送テストを開始</a></p>'
                '<p>REPL で転送時間(ms)と KB/s を確認してください</p>'
                '</body></html>'
            )
            resp = (
                'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n'
                f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}'
            )
            writer.write(resp.encode())
            await writer.drain()

    except Exception as e:
        print('handle error:', e)
    finally:
        writer.close()
        await writer.wait_closed()

async def main():
    setup_ap()
    server = await uasyncio.start_server(handle, '0.0.0.0', PORT)
    print(f'サーバー起動: http://{IP}/')
    print('ブラウザで http://192.168.4.1/bench にアクセスしてください')
    async with server:
        await server.wait_closed()

uasyncio.run(main())
