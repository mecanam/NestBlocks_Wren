# Phase 0 / P4 — _thread + HTTP サーバー同時動作テスト (Pico W 側)
# main.py として書き込む
#
# テスト内容:
#   core1: カウントループ (擬似的な生徒プログラム)
#   core0: HTTP サーバー (クライアントのリクエストに応答し続ける)
#
# 判定基準: HTTP サーバーが core1 稼働中も応答を維持すること
# PC 側で p3_client.py ではなく curl / ブラウザで /ping を連打して確認

import network
import uasyncio
import _thread
import utime

SSID     = 'Wren-BENCH'
PASSWORD = 'bench1234'
IP       = '192.168.4.1'
PORT     = 80

# ── core1 で動かす擬似生徒プログラム ──────────
_core1_running = True
_core1_count   = 0

def core1_program():
    global _core1_count
    while _core1_running:
        _core1_count += 1
        utime.sleep_ms(10)   # GPIO 操作を模擬
# ─────────────────────────────────────────────

def setup_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(ssid=SSID, password=PASSWORD, channel=1,
              security=network.AUTH_WPA2_PSK)
    ap.ifconfig((IP, '255.255.255.0', IP, IP))
    while not ap.active():
        utime.sleep_ms(100)
    print(f'AP 起動: {SSID}  ip={IP}')

async def handle(reader, writer):
    try:
        req = await reader.read(256)
        first = req.split(b'\r\n')[0].decode()
        path = first.split(' ')[1] if ' ' in first else '/'

        if path == '/ping':
            body = f'pong  core1_count={_core1_count}'
            resp = (
                'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n'
                f'Content-Length: {len(body)}\r\nConnection: close\r\n\r\n{body}'
            )
        else:
            body = (
                '<html><body>'
                '<h1>P4 Thread Test</h1>'
                '<p>core1 が擬似プログラムを動かしながら</p>'
                '<p>このサーバーが応答を返しています</p>'
                '<p><a href="/ping">/ping を繰り返し叩いてレスポンスを確認</a></p>'
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

async def monitor():
    prev = 0
    while True:
        await uasyncio.sleep(5)
        delta = _core1_count - prev
        prev  = _core1_count
        print(f'[P4] core1_count={_core1_count}  +{delta}/5s  '
              f'({"OK" if delta > 0 else "STOPPED!"})')

async def main():
    setup_ap()

    # core1 起動
    _thread.start_new_thread(core1_program, ())
    print('core1 起動済み')

    server = await uasyncio.start_server(handle, '0.0.0.0', PORT)
    print(f'HTTP サーバー起動: http://{IP}/')
    print('判定: http://192.168.4.1/ping を連打して "pong" が返ることを確認')

    uasyncio.create_task(monitor())

    async with server:
        await server.wait_closed()

uasyncio.run(main())
