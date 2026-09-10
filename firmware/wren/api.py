# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# api.py — /api/* ハンドラ (仕様書 §5.1, §6.2, §6.3)
#
# ルーティングは server.py から呼ばれる:
#   await api_handle(method, path, query, body, headers, writer, send_json)
#
# エンドポイント一覧:
#   GET  /api/info          ← ボード情報
#   GET  /api/state         ← 実行状態
#   POST /api/program       ← プログラムの保存 (コンパイル済み MicroPython)
#   POST /api/run           ← TEST 実行開始
#   POST /api/stop          ← TEST 停止
#   POST /api/reset         ← ソフトリセット
#   POST /api/mode/run      ← RUN モードへ切り替え
#   GET  /api/console       ← コンソール出力のポーリング
#   GET  /api/projects      ← プロジェクト一覧
#   POST /api/projects      ← プロジェクト保存
#   GET  /api/projects/{id} ← プロジェクト取得
#   DELETE /api/projects/{id} ← プロジェクト削除

import json
import os
from . import config, runner, console as _console, storage

# LED コルーチンは main.py が差し替える
_led_switch = None

def set_led_switch(fn):
    """main.py から LED 切り替え関数を登録する。"""
    global _led_switch
    _led_switch = fn

# ── クエリパーサー ─────────────────────────────────────────────
def _parse_query(query):
    """'key=val&key2=val2' を dict に変換する。"""
    result = {}
    if not query:
        return result
    for part in query.split('&'):
        if '=' in part:
            k, _, v = part.partition('=')
            result[k] = v
    return result

# ── モード永続化 ───────────────────────────────────────────────
def _write_mode(mode):
    with open('/mode.txt', 'w') as f:
        f.write(mode)

# ── メインディスパッチャ ───────────────────────────────────────
async def handle(method, path, query, body, headers, writer, send_json):
    """server.py から呼ばれる非同期ハンドラ。"""

    # ── /api/info ─────────────────────────────────────────────
    if path == '/api/info' and method == 'GET':
        import machine
        mem = gc_stats()
        await send_json(writer, '200 OK', {
            'version': config.VERSION,
            'edition': config.EDITION,
            'ssid':    config.SSID,
            'ip':      config.IP,
            'mem_free':  mem['free'],
            'mem_alloc': mem['alloc'],
        })
        return

    # ── /api/state ────────────────────────────────────────────
    if path == '/api/state' and method == 'GET':
        await send_json(writer, '200 OK', {
            'running':    runner.is_running(),
            'last_error': runner.last_error(),
            'console_seq': _console.latest_seq(),
        })
        return

    # ── /api/console ──────────────────────────────────────────
    if path == '/api/console' and method == 'GET':
        params = _parse_query(query)
        try:
            since = int(params.get('since', 0))
        except ValueError:
            since = 0
        entries = _console.since(since)
        await send_json(writer, '200 OK', {
            'entries': [{'seq': s, 'text': t} for s, t in entries],
            'latest_seq': _console.latest_seq(),
        })
        return

    # ── /api/program ──────────────────────────────────────────
    if path == '/api/program' and method == 'POST':
        if not body:
            await send_json(writer, '400 Bad Request', {'error': 'empty body'})
            return
        try:
            data = json.loads(body)
            code = data.get('code', '')
        except Exception:
            await send_json(writer, '400 Bad Request', {'error': 'invalid JSON'})
            return
        if not code:
            await send_json(writer, '400 Bad Request', {'error': 'no code'})
            return
        with open('/user_program.py', 'w') as f:
            f.write(code)
        await send_json(writer, '200 OK', {'ok': True})
        return

    # ── /api/run ──────────────────────────────────────────────
    if path == '/api/run' and method == 'POST':
        # 実行中なら自動停止してから再実行
        if runner.is_running():
            await runner.stop()
        try:
            with open('/user_program.py', 'r') as f:
                code = f.read()
        except OSError:
            await send_json(writer, '404 Not Found', {'error': 'no program'})
            return

        def _led_double():
            if _led_switch:
                from . import led
                _led_switch(led.double_blink())

        ok = runner.start(code, _led_double)
        if ok:
            await send_json(writer, '200 OK', {'ok': True})
        else:
            await send_json(writer, '500 Internal Server Error',
                            {'error': 'start failed'})
        return

    # ── /api/stop ─────────────────────────────────────────────
    if path == '/api/stop' and method == 'POST':
        def _led_slow():
            if _led_switch:
                from . import led
                _led_switch(led.slow_blink())

        was_running = runner.is_running()
        await runner.stop(led_switch_fn=_led_slow)
        await send_json(writer, '200 OK', {'ok': True, 'was_running': was_running})
        return

    # ── /api/reset ────────────────────────────────────────────
    if path == '/api/reset' and method == 'POST':
        import machine
        await send_json(writer, '200 OK', {'ok': True})
        import uasyncio
        await uasyncio.sleep_ms(200)
        machine.reset()
        return

    # ── /api/mode/run ─────────────────────────────────────────
    if path == '/api/mode/run' and method == 'POST':
        if runner.is_running():
            await send_json(writer, '409 Conflict',
                            {'error': 'stop program before switching mode'})
            return
        _write_mode('run')
        await send_json(writer, '200 OK', {'ok': True})
        import uasyncio, machine
        await uasyncio.sleep_ms(200)
        machine.reset()
        return

    # ── /api/export ───────────────────────────────────────────
    # POST: ダウンロード用データを一時保存
    # GET:  Content-Disposition: attachment で配信 (iOS Safari 対応)
    if path == '/api/export':
        if method == 'POST':
            if not body:
                await send_json(writer, '400 Bad Request', {'error': 'empty body'})
                return
            try:
                data     = json.loads(body)
                filename = data.get('filename', 'project.xml')
                content  = data.get('data', '')
            except Exception:
                await send_json(writer, '400 Bad Request', {'error': 'invalid JSON'})
                return
            with open('/export.tmp', 'w') as f:
                f.write(json.dumps({'filename': filename, 'data': content}))
            await send_json(writer, '200 OK', {'ok': True})
            return

        if method == 'GET':
            try:
                with open('/export.tmp', 'r') as f:
                    d = json.loads(f.read())
                filename = d.get('filename', 'project.xml')
                content  = d.get('data', '')
            except OSError:
                await send_json(writer, '404 Not Found', {'error': 'no export'})
                return
            body_bytes = content.encode('utf-8')
            safe_name  = filename.replace('"', '_').replace('\\', '_')
            resp_head  = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: application/octet-stream\r\n'
                f'Content-Disposition: attachment; filename="{safe_name}"\r\n'
                f'Content-Length: {len(body_bytes)}\r\n'
                'Cache-Control: no-store\r\n'
                'Access-Control-Allow-Origin: *\r\n'
                'Connection: close\r\n'
                '\r\n'
            )
            writer.write(resp_head.encode('utf-8'))
            writer.write(body_bytes)
            await writer.drain()
            return

    # ── /api/projects ─────────────────────────────────────────
    if path == '/api/projects':
        if method == 'GET':
            await send_json(writer, '200 OK', storage.list_projects())
            return
        if method == 'POST':
            if not body:
                await send_json(writer, '400 Bad Request', {'error': 'empty body'})
                return
            try:
                data = json.loads(body)
            except Exception:
                await send_json(writer, '400 Bad Request', {'error': 'invalid JSON'})
                return
            saved = storage.save_project(data)
            await send_json(writer, '200 OK', saved)
            return

    # ── /api/projects/{id} ────────────────────────────────────
    if path.startswith('/api/projects/'):
        pid = path[len('/api/projects/'):]
        if not pid:
            await send_json(writer, '400 Bad Request', {'error': 'missing id'})
            return

        if method == 'GET':
            proj = storage.get_project(pid)
            if proj is None:
                await send_json(writer, '404 Not Found', {'error': 'not found'})
            else:
                await send_json(writer, '200 OK', proj)
            return

        if method == 'PUT' or method == 'POST':
            if not body:
                await send_json(writer, '400 Bad Request', {'error': 'empty body'})
                return
            try:
                data = json.loads(body)
            except Exception:
                await send_json(writer, '400 Bad Request', {'error': 'invalid JSON'})
                return
            data['id'] = pid
            saved = storage.save_project(data)
            await send_json(writer, '200 OK', saved)
            return

        if method == 'DELETE':
            ok = storage.delete_project(pid)
            if ok:
                await send_json(writer, '200 OK', {'ok': True})
            else:
                await send_json(writer, '404 Not Found', {'error': 'not found'})
            return

    # ── 未知のエンドポイント ──────────────────────────────────
    await send_json(writer, '404 Not Found', {'error': f'unknown: {method} {path}'})

# ── ユーティリティ ─────────────────────────────────────────────
def gc_stats():
    import gc
    gc.collect()
    return {'free': gc.mem_free(), 'alloc': gc.mem_alloc()}
