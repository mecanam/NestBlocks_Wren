# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# runner.py — TEST 実行エンジン
#
# 実行フロー:
#   core0 の uasyncio タスクとしてユーザープログラムを実行する。
#   await uasyncio.sleep() が HTTP サーバーに制御を返すため GIL ブロックが起きない。
#
# 停止フロー:
#   _stop_flag → _nb.check() が _StopRequest を送出、または task.cancel()
#   finally ブロックで全 PWM/Pin 出力をゼロにリセット
#   5 秒タイムアウト後 → machine.reset()

import uasyncio
import time
import builtins as _builtins
from . import console as _console

# ── 内部状態 ──────────────────────────────────────────────────
_running       = False
_stop_flag     = False
_last_error    = None
_need_led_slow = False
_user_tasks    = []   # run_async が作成したユーザータスク (stop() からキャンセル用)
_active_globals = None
_output_refs = []     # 終了後の停止操作でも出力を再確認するために保持
_pwm_pins = set()     # 生成コードが実際に初期化した PWM ピン

def is_running():
    return _running

def last_error():
    return _last_error

def take_led_slow():
    global _need_led_slow
    if _need_led_slow:
        _need_led_slow = False
        return True
    return False

# ── 停止シグナル ───────────────────────────────────────────────
class _StopRequest(BaseException):
    pass

# ── _nb モジュール (exec globals に渡す) ──────────────────────
class _NbModule:
    def check(self):
        if _stop_flag:
            raise _StopRequest()

_nb = _NbModule()

# ── print キャプチャ ──────────────────────────────────────────
def _capture_print(*args, sep=' ', end='\n', **kwargs):
    text = sep.join(str(a) for a in args) + end.rstrip('\n')
    _console.push(text)

# ── 出力リセット ──────────────────────────────────────────────
def _reset_outputs(g=None):
    """生成コードの辞書・リスト・タプル内も含め、PWM と GPIO を停止する。"""
    global _output_refs
    try:
        from machine import PWM, Pin
    except Exception:
        return
    if g is not None:
        # PWM.deinit() はスライスを停止するだけなので、使用ピンも GPIO LOW に戻す。
        for name, value in g.items():
            if isinstance(value, PWM) and name.startswith('pwm_'):
                try:
                    _pwm_pins.add(int(name[4:]))
                except ValueError:
                    pass
        for cache_name, pins_name in (('_motor_pwm', '_MOTOR_PINS'), ('_servo_pwm', '_SERVO_PINS')):
            cache, mapping = g.get(cache_name, {}), g.get(pins_name, {})
            if isinstance(cache, dict) and isinstance(mapping, dict):
                for channel in cache:
                    pins = mapping.get(channel, ())
                    if isinstance(pins, int):
                        pins = (pins,)
                    if isinstance(pins, (tuple, list)):
                        for pin in pins:
                            if isinstance(pin, int):
                                _pwm_pins.add(pin)
    for pin in _pwm_pins:
        try:
            Pin(pin, Pin.OUT, value=0)
        except Exception as e:
            _console.push('[Wren] PWM ピン停止エラー: ' + str(e))
    pending = [g] if g is not None else []
    seen = set()
    outputs = list(_output_refs)
    output_ids = set(id(v) for v in outputs)
    while pending:
        v = pending.pop()
        identity = id(v)
        if identity in seen:
            continue
        seen.add(identity)
        if isinstance(v, (PWM, Pin)):
            if identity not in output_ids:
                outputs.append(v)
                output_ids.add(identity)
        elif isinstance(v, dict):
            pending.extend(v.values())
        elif isinstance(v, (list, tuple)):
            pending.extend(v)
    _output_refs = outputs
    # 同じ PWM スライスを使う出力も、先にすべて duty=0 にする。
    for v in outputs:
        try:
            if isinstance(v, PWM):
                v.duty_u16(0)
            else:
                v.value(0)  # 入力ピンを出力モードに変更しない
        except Exception as e:
            _console.push('[Wren] 出力停止エラー: ' + str(e))
    for v in outputs:
        if isinstance(v, PWM):
            try:
                v.deinit()
            except Exception as e:
                _console.push('[Wren] PWM 停止エラー: ' + str(e))

# ── asyncio タスク ────────────────────────────────────────────
async def run_async(code_str, led_switch_fn=None):
    global _running, _stop_flag, _last_error, _need_led_slow, _user_tasks
    global _active_globals, _output_refs, _pwm_pins

    _console.reset()
    _console.push('[Wren] 実行開始')
    _running    = True
    _stop_flag  = False
    _last_error = None
    _user_tasks = []
    _output_refs = []
    _pwm_pins = set()

    if led_switch_fn:
        led_switch_fn()

    # exec 内で uasyncio.run() / import uasyncio を除去する。
    # 文字列置換は改行差異で失敗するため、行単位でフィルタリングする。
    _SKIP = ('import uasyncio', 'from uasyncio import')
    lines = code_str.split('\n')
    exec_lines = []
    for _l in lines:
        _s = _l.strip()
        if _s in _SKIP or _s.startswith('uasyncio.run('):
            continue
        exec_lines.append(_l)
    exec_code = '\n'.join(exec_lines)

    _g = {
        '__builtins__': _builtins,
        '_nb':          _nb,
        'print':        _capture_print,
        'uasyncio':     uasyncio,
    }
    _active_globals = _g

    try:
        exec(exec_code, _g)
        # task_0, task_1 ... を独立した Task として create_task で実行する。
        # サブコルーチン埋め込み (await coros[0]) は MicroPython uasyncio で
        # sleep の yield が正しく伝播しないため、create_task を必ず使う。
        task_fns = sorted(
            [(k, v) for k, v in _g.items() if k.startswith('task_') and callable(v)],
            key=lambda x: x[0]
        )
        _console.push('[DBG] tasks=' + str([k for k, _ in task_fns]))
        if task_fns:
            tasks = [uasyncio.create_task(fn()) for _, fn in task_fns]
            _user_tasks = tasks
            while True:
                alive = [t for t in tasks if not t.done()]
                if not alive:
                    break
                if _stop_flag:
                    for t in alive:
                        try:
                            t.cancel()
                        except Exception:
                            pass
                    # キャンセルが実行される猶予を与える
                    await uasyncio.sleep_ms(100)
                    break
                await uasyncio.sleep_ms(100)
        elif 'main' in _g:
            await _g['main']()
        _last_error = None
    except _StopRequest:
        _last_error = None
        _console.push('[Wren] 停止しました')
    except BaseException as e:
        if _stop_flag:
            _last_error = None
            _console.push('[Wren] 停止しました')
        else:
            import sys, io
            buf = io.StringIO()
            sys.print_exception(e, buf)
            _last_error = buf.getvalue()
            first_line = _last_error.split('\n')[0] if _last_error else str(e)
            _console.push(f'[エラー] {first_line}')
            _console.push(_last_error)
    finally:
        _reset_outputs(_g)
        _active_globals = None
        _user_tasks    = []
        _running       = False
        _stop_flag     = False
        _need_led_slow = True

# ── 公開 API ──────────────────────────────────────────────────
def start(code_str, led_switch_fn=None):
    global _running

    if _running:
        return False

    uasyncio.create_task(run_async(code_str, led_switch_fn))
    return True

async def stop(led_switch_fn=None, timeout_ms=5000):
    """実行中のプログラムを停止する。
    ユーザータスクを即座にキャンセルし、cooperative stop → タイムアウト後 machine.reset()。
    """
    global _stop_flag

    # await より先に出力を止め、タスク終了時にも finally でもう一度停止する。
    _reset_outputs(_active_globals)
    if not _running:
        if led_switch_fn:
            led_switch_fn()
        return True

    _stop_flag = True

    # ユーザータスクをキャンセル (await sleep_ms 中でも即座に中断)
    for t in _user_tasks:
        try:
            t.cancel()
        except Exception:
            pass

    deadline = time.ticks_add(time.ticks_ms(), timeout_ms)
    while _running:
        if time.ticks_diff(deadline, time.ticks_ms()) <= 0:
            break
        await uasyncio.sleep_ms(100)

    if not _running:
        if led_switch_fn:
            led_switch_fn()
        return True

    _console.push('[Wren] 強制リセットします')
    await uasyncio.sleep_ms(200)
    import machine
    machine.reset()
    return False
