# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# led.py — LED パターン
# 仕様書 §7.4 に対応する点滅パターンをコルーチンで実装する。

import uasyncio
from machine import Pin

_led = Pin('LED', Pin.OUT)

# 外部からキャンセルできるように現在のタスクを保持
_current = None

def _cancel_current():
    global _current
    if _current and not _current.done():
        _current.cancel()
    _current = None

async def fast_blink():
    """起動中: 速い点滅"""
    _cancel_current()
    while True:
        _led.value(1); await uasyncio.sleep_ms(100)
        _led.value(0); await uasyncio.sleep_ms(100)

async def slow_blink():
    """EDIT モード・クライアント未接続: ゆっくり点滅"""
    while True:
        _led.value(1); await uasyncio.sleep_ms(800)
        _led.value(0); await uasyncio.sleep_ms(800)

async def solid():
    """EDIT モード・クライアント接続中: 点灯"""
    _led.value(1)
    while True:
        await uasyncio.sleep_ms(1000)

async def double_blink():
    """プログラム実行中: 2 回点滅の繰り返し"""
    while True:
        for _ in range(2):
            _led.value(1); await uasyncio.sleep_ms(150)
            _led.value(0); await uasyncio.sleep_ms(150)
        await uasyncio.sleep_ms(800)

def off():
    """RUN モード: 消灯 (コルーチン不要)"""
    _led.value(0)

def switch(task_coro, loop=None):
    """現在の LED タスクをキャンセルして新しいパターンを開始する。"""
    global _current
    _cancel_current()
    _current = uasyncio.create_task(task_coro)
    return _current
