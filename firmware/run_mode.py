# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# run_mode.py — RUN モード (BLE + /user_program.py 実行)
# boot.py から import される。
# uasyncio.run() がブロックするため main.py は実行されない。

import uasyncio
import gc
from machine import Pin

# LED 消灯 (RUN モードは LED OFF)
Pin('LED', Pin.OUT).value(0)

gc.collect()

try:
    with open('/user_program.py', 'r') as f:
        _code = f.read()
except OSError:
    print('[RUN] /user_program.py が見つかりません。EDIT モードで書き込んでください。')
    import machine
    machine.reset()

# _nb モジュール (wren_generators.js がループに注入する _nb.check() 用)
class _NbModule:
    def check(self):
        pass  # RUN モードは停止チェック不要

_nb = _NbModule()

# 生徒プログラムをそのまま実行する。
# プログラム内の uasyncio.run(ble.start(main())) がここでブロックする。
try:
    exec(_code, {'__name__': '__main__', '_nb': _nb})
except Exception as e:
    import sys
    sys.print_exception(e)
    print('[RUN] エラーが発生しました。3 秒後に EDIT モードで再起動します。')
    import utime
    utime.sleep(3)
    import machine
    machine.reset()
