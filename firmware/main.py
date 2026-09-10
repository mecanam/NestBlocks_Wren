# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# main.py — EDIT モードのエントリーポイント
# boot.py が EDIT モードと判断した場合に実行される

import uasyncio
import network
import gc
from wren import config, led, dns, portal, server, api, storage, console, runner

async def _setup_ap():
    """Wi-Fi AP を起動して IP アドレスを設定する。"""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(
        ssid     = config.SSID,
        password = config.PASSWORD,
        channel  = config.CHANNEL,
        pm       = network.WLAN.PM_NONE,  # 省電力 OFF (接続安定化)
    )
    ap.ifconfig((config.IP, '255.255.255.0', config.IP, config.IP))

    timeout = 50  # 5 秒
    while not ap.active() and timeout > 0:
        await uasyncio.sleep_ms(100)
        timeout -= 1

    print(f'[Wren] AP 起動: ssid={config.SSID}  ip={config.IP}')
    return ap

async def main():
    gc.collect()

    # ── AP 起動 ───────────────────────────────────────────────
    await _setup_ap()

    # ── ストレージ初期化 ──────────────────────────────────────
    storage.init()

    # ── LED: ゆっくり点滅 (EDIT モード・待機中) ──────────────
    led_task = uasyncio.create_task(led.slow_blink())

    # api.py が LED を切り替えられるよう led.switch を渡す
    api.set_led_switch(led.switch)

    # ── LED ウォッチドッグ: プログラム終了時に slow_blink へ戻す ─
    async def _led_watchdog():
        while True:
            if runner.take_led_slow():
                led.switch(led.slow_blink())
            await uasyncio.sleep_ms(300)

    # ── LED ウォッチドッグ起動 ────────────────────────────────
    uasyncio.create_task(_led_watchdog())

    # ── DNS サーバー (キャプティブポータル対応) ───────────────
    dns_task = uasyncio.create_task(dns.serve())

    # ── HTTP サーバー ─────────────────────────────────────────
    srv = await server.create(
        host    = '0.0.0.0',
        port    = 80,
        routes  = {
            'api':    api.handle,
            'portal': portal.handle,
        },
        led_task = led_task,
    )

    print(f'[Wren] 準備完了 → http://{config.IP}/')

    async with srv:
        await srv.wait_closed()

uasyncio.run(main())
