// wren_api_client.js — NestSerial 互換の fetch() ベース API クライアント
// WebSerial を使わず HTTP API 経由で Pico W と通信する。
// NestSerial と同一インターフェースを持ち、main.js を無改変で動作させる。

(function () {
  'use strict';

  var BASE = '';   // 同一オリジン (http://192.168.4.1/)
  var _connected = false;

  function _fetch(method, path, body) {
    var opts = {
      method: method,
      headers: { 'Content-Type': 'application/json' },
    };
    if (body !== undefined) {
      opts.body = JSON.stringify(body);
    }
    return fetch(BASE + path, opts).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (e) {
          throw new Error(e.error || ('HTTP ' + r.status));
        });
      }
      return r.json();
    });
  }

  var NestSerial = {
    // ── 接続 ─────────────────────────────────────────────────
    isConnected: function () { return _connected; },

    connect: function () {
      return _fetch('GET', '/api/info').then(function (info) {
        _connected = true;
        console.log('[Wren] 接続:', info.ssid, 'v' + info.version);
        return info;
      });
    },

    disconnect: function () {
      _connected = false;
      return Promise.resolve();
    },

    // ── コード実行 (TEST モード) ──────────────────────────────
    executeCode: function (code) {
      return _fetch('POST', '/api/program', { code: code }).then(function () {
        return _fetch('POST', '/api/run');
      });
    },

    // ── 停止 ─────────────────────────────────────────────────
    stopExecution: function () {
      return _fetch('POST', '/api/stop');
    },

    // ── コード書き込み (RUN モード用: /user_program.py に保存) ─
    uploadCode: function (code) {
      return _fetch('POST', '/api/program', { code: code });
    },

    // ── 状態取得 (拡張 API) ──────────────────────────────────
    getState: function () {
      return _fetch('GET', '/api/state');
    },

    // ── ソフトリセット ────────────────────────────────────────
    reset: function () {
      return _fetch('POST', '/api/reset');
    },

    // ── RUN モード切り替え ────────────────────────────────────
    switchToRunMode: function () {
      return _fetch('POST', '/api/mode/run');
    },

    // ── main.js 互換スタブ (コールバック登録 — Wren では未使用) ─
    setOnData:       function () {},
    setOnDisconnect: function () {},
    setOnConnect:    function () {},
  };

  window.NestSerial = NestSerial;
})();
