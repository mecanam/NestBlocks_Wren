# Phase 0 / P3 — HTTP 転送速度ベンチ (PC 側)
# PC を Wren-BENCH AP に接続してから実行する
# python p3_client.py
#
# 判定基準: elapsed < 20 秒

import urllib.request
import time

URL = 'http://192.168.4.1/bench'
EXPECTED = 356 * 1024

print(f'接続先: {URL}')
print(f'期待サイズ: {EXPECTED // 1024} KB')
print('計測開始...')

t0 = time.perf_counter()
try:
    with urllib.request.urlopen(URL, timeout=60) as resp:
        data = resp.read()
    elapsed = time.perf_counter() - t0

    size = len(data)
    rate = size / elapsed / 1024  # KB/s

    print()
    print('=' * 40)
    print('P3 — HTTP 転送速度ベンチ結果')
    print('=' * 40)
    print(f'  受信サイズ : {size:,} B  ({size / 1024:.1f} KB)')
    print(f'  所要時間   : {elapsed:.2f} 秒')
    print(f'  転送速度   : {rate:.1f} KB/s')
    print()
    if elapsed <= 10:
        print('  [PASS ★] 10 秒以内 — 推奨目標クリア')
    elif elapsed <= 20:
        print('  [PASS]   20 秒以内 — 最低基準クリア')
    else:
        print('  [FAIL]   20 秒超過 — Blockly カスタムビルドを検討')
    print('=' * 40)

except Exception as e:
    elapsed = time.perf_counter() - t0
    print(f'\n[ERROR] {e}  ({elapsed:.1f} 秒後)')
    print('Wren-BENCH AP に接続されているか確認してください')
