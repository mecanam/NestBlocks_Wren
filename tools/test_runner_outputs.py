"""PC 上で停止時の出力処理を確認: python -B tools/test_runner_outputs.py"""
import asyncio
import sys
import time
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'firmware'))
sys.modules['uasyncio'] = asyncio
asyncio.sleep_ms = lambda ms: asyncio.sleep(ms / 1000)
time.ticks_ms = lambda: int(time.monotonic() * 1000)
time.ticks_add = lambda a, b: a + b
time.ticks_diff = lambda a, b: a - b


class Pin:
    OUT = 1
    IN = 0
    forced = {}

    def __init__(self, number, mode=OUT, value=None):
        self.number, self.mode, self.level = number, mode, 1 if value is None else value
        if value is not None:
            self.forced[number] = (mode, value)

    def value(self, level):
        self.level = level


class PWM:
    instances = []

    def __init__(self, pin):
        self.pin = pin
        self.duty = 40000
        self.enabled = True
        self.instances.append(self)

    def duty_u16(self, value):
        self.duty = value

    def deinit(self):
        self.enabled = False


sys.modules['machine'] = types.SimpleNamespace(Pin=Pin, PWM=PWM)
from wren import runner, api


class OutputsTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        PWM.instances = []
        Pin.forced = {}
        runner._pwm_pins = set()
        runner._output_refs = []
        runner._active_globals = None
        runner._running = False
        runner._stop_flag = False
        runner._user_tasks = []

    def assert_stopped(self):
        self.assertTrue(PWM.instances)
        for output in PWM.instances:
            self.assertEqual(output.duty, 0)
            self.assertFalse(output.enabled)

    def test_nested_motor_servo_and_gpio(self):
        fin, rin, servo = [PWM(Pin(n)) for n in (8, 9, 10)]
        output, sensor = Pin(12), Pin(13, Pin.IN)
        unrelated = Pin(22, Pin.IN)
        g = {'_motor_pwm': {1: (fin, rin)}, '_servo_pwm': {1: servo}, 'pins': [output, sensor],
             '_MOTOR_PINS': {1: (8, 9), 2: (14, 15)}, '_SERVO_PINS': {1: 10}}
        g['cycle'] = g
        g['alias'] = fin
        runner._reset_outputs(g)
        self.assert_stopped()
        self.assertEqual(output.level, 0)
        self.assertEqual(sensor.mode, Pin.IN)
        self.assertEqual(unrelated.level, 1)
        self.assertEqual(Pin.forced, {8: (Pin.OUT, 0), 9: (Pin.OUT, 0), 10: (Pin.OUT, 0)})

    def test_generated_pwm_pin_forced_low(self):
        runner._reset_outputs({'pwm_16': PWM(Pin(16))})
        self.assert_stopped()
        self.assertEqual(Pin.forced, {16: (Pin.OUT, 0)})

    def test_failure_does_not_skip_other_outputs(self):
        broken, good = PWM(Pin(8)), PWM(Pin(9))
        def fail(value):
            raise OSError('failed')
        broken.duty_u16 = fail
        runner._reset_outputs({'outputs': [broken, good]})
        self.assertFalse(broken.enabled)
        self.assertEqual(good.duty, 0)
        self.assertFalse(good.enabled)

    async def test_normal_completion(self):
        await runner.run_async('from machine import Pin, PWM\n_motor_pwm = {1: (PWM(Pin(8)), PWM(Pin(9)))}')
        self.assert_stopped()

    async def test_stop_during_motor_execution(self):
        code = '''from machine import Pin, PWM
_motor_pwm = {}
async def task_0():
    _motor_pwm[1] = (PWM(Pin(8)), PWM(Pin(9)))
    try:
        await uasyncio.sleep(60)
    finally:
        _motor_pwm[1][0].duty_u16(10000)
'''
        task = asyncio.create_task(runner.run_async(code))
        for _ in range(20):
            if PWM.instances:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(PWM.instances)
        stopping = asyncio.create_task(runner.stop(timeout_ms=1000))
        await asyncio.sleep(0)
        self.assert_stopped()  # キャンセル待ちの前に停止
        self.assertTrue(await stopping)
        await task
        self.assert_stopped()  # ユーザーの finally が再出力しても停止
        self.assertFalse(runner.is_running())

    async def test_idle_stop_rechecks_outputs(self):
        pwm = PWM(Pin(8))
        runner._output_refs = [pwm]
        await runner.stop()
        self.assert_stopped()

    async def test_idle_api_still_resets_outputs(self):
        pwm = PWM(Pin(8))
        runner._output_refs = [pwm]
        responses = []
        async def send_json(writer, status, body):
            responses.append((status, body))
        await api.handle('POST', '/api/stop', '', b'', {}, None, send_json)
        self.assert_stopped()
        self.assertEqual(responses[0][1], {'ok': True, 'was_running': False})

    async def test_run_again_after_stop(self):
        code = 'from machine import Pin, PWM\n_motor_pwm = {1: (PWM(Pin(8)), PWM(Pin(9)))}'
        await runner.run_async(code)
        await runner.stop()
        await runner.run_async(code)
        self.assertEqual(len(PWM.instances), 4)
        self.assert_stopped()


if __name__ == '__main__':
    unittest.main()
