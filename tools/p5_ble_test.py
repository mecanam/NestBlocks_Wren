# Phase 0 / P5 — BLE 安定性テスト (Pico W 側)
# WiFi AP を立てずに BLE だけ起動し、GamePad と接続して
# 一定時間の通信安定性を確認する
#
# 前提: piconest_ble ライブラリが Pico W に書き込まれていること
#       (USB 版 NestBlocks で BLE ブロックを書き込んだ実績があるもの)
#
# 判定基準: 5 分間、通信が途切れずに継続すること
#
# 使い方:
#   1. main.py として書き込む (WiFi は起動しない)
#   2. GamePad コントローラーをペアリング
#   3. REPL でカウント増加・エラーなしを確認

import uasyncio
import utime

# piconest_ble を想定 (USB 版と同じライブラリ)
try:
    from piconest_ble import NestBLE
    BLE_AVAILABLE = True
except ImportError:
    BLE_AVAILABLE = False
    print('[P5] piconest_ble が見つかりません')
    print('     USB 版で書き込み済みの Pico W を使用してください')

_recv_count  = 0
_error_count = 0
_last_recv   = utime.ticks_ms()
_TIMEOUT_MS  = 10_000   # 10 秒受信なしでタイムアウト警告

def on_data(data):
    global _recv_count, _last_recv
    _recv_count += 1
    _last_recv = utime.ticks_ms()

async def monitor():
    global _error_count
    start = utime.ticks_ms()
    TARGET_SEC = 300   # 5 分

    while True:
        await uasyncio.sleep(10)
        elapsed = utime.ticks_diff(utime.ticks_ms(), start) // 1000
        since   = utime.ticks_diff(utime.ticks_ms(), _last_recv)

        timeout = since > _TIMEOUT_MS
        if timeout:
            _error_count += 1

        status = 'TIMEOUT!' if timeout else 'OK'
        print(f'[P5] {elapsed:4d}s  受信={_recv_count:6d}  エラー={_error_count}  {status}')

        if elapsed >= TARGET_SEC:
            print()
            print('=' * 40)
            print('P5 — BLE 安定性テスト 結果')
            print('=' * 40)
            print(f'  計測時間 : {elapsed} 秒')
            print(f'  受信パケット: {_recv_count}')
            print(f'  タイムアウト: {_error_count} 回')
            if _error_count == 0:
                print('  [PASS] 安定して通信継続')
            else:
                print('  [FAIL] 通信断が発生 — 2 モード制設計の見直しが必要')
            print('=' * 40)
            return

async def main():
    if not BLE_AVAILABLE:
        return

    print('BLE のみ起動 (WiFi なし)')
    ble = NestBLE()
    ble.on_receive(on_data)

    print('GamePad をペアリングしてください...')
    await ble.start()

    uasyncio.create_task(monitor())

    # メインループ (BLE がバックグラウンドで動く)
    while True:
        await uasyncio.sleep_ms(100)

uasyncio.run(main())
