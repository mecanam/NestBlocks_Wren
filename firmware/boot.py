# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# boot.py — モード判定とルーティング
# MicroPython の起動順: boot.py → main.py
#
# EDIT モード: そのまま main.py へ
# RUN  モード: run_mode.py を import → uasyncio.run() で main.py を阻止
#
# モード判定の優先順位:
#   1. RUN_PIN (GP22) が HIGH → 強制 RUN モード
#   2. /mode.txt が 'run'     → 一時 RUN モード (次回起動は EDIT に戻る)
#   3. それ以外               → EDIT モード

import sys
sys.path.insert(0, '/wren')   # wren パッケージを検索パスに追加

# ── RUN ピン判定 ──────────────────────────────────────────────
# GP22 に内部プルダウンを設定。HIGH (3.3V 入力) で RUN モード強制起動。
# ピン未接続 / LOW の場合は EDIT モード (mode.txt の判定に進む)。
from machine import Pin
import utime

_RUN_PIN = Pin(22, Pin.IN, Pin.PULL_DOWN)
utime.sleep_ms(10)   # プルダウン安定待ち

if _RUN_PIN.value() == 1:
    # ピンが HIGH → 強制 RUN モード (mode.txt は変更しない)
    import run_mode  # noqa: F401
else:
    # ── /mode.txt の読み書き ──────────────────────────────────
    def _read_mode():
        try:
            with open('/mode.txt', 'r') as f:
                return f.read().strip()
        except OSError:
            return 'edit'

    def _write_mode(m):
        with open('/mode.txt', 'w') as f:
            f.write(m)

    _mode = _read_mode()

    if _mode == 'run':
        # 安全装置: 先に 'edit' に書き戻す
        # → 電源を入れ直せば必ず EDIT モードに戻る
        _write_mode('edit')

        # RUN モードを実行 (uasyncio.run() がブロックし main.py は走らない)
        import run_mode  # noqa: F401
    else:
        # EDIT モード: main.py に委譲 (何もしない)
        pass
