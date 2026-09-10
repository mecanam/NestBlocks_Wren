// wren_main_patch.js — Wren 向け main.js 差し替えパッチ

(function () {
  'use strict';

  // ── コンソールポーリング ──────────────────────────────────
  var _pollSeq   = 0;
  var _pollTimer = null;
  var _POLL_MS   = 300;

  function _startConsolePolling() {
    if (_pollTimer) return;
    _pollSeq   = 0;
    _pollTimer = setInterval(_pollConsole, _POLL_MS);
  }

  function _stopConsolePolling() {
    clearInterval(_pollTimer);
    _pollTimer = null;
  }

  function _pollConsole() {
    fetch('/api/console?since=' + _pollSeq)
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var entries = data.entries || [];
        console.log('[poll] since=' + _pollSeq + ' -> ' + entries.length + ' entries');
        for (var i = 0; i < entries.length; i++) {
          var text = entries[i].text;
          var cls  = text.indexOf('[エラー]') === 0 ? 'err' : '';
          logToConsole(text, cls);
          if (cls === 'err') toast('実行エラー: ' + text.replace('[エラー] ', '').substring(0, 60));
          _pollSeq = entries[i].seq + 1;
        }
        if (!_pollTimer) return;
        if (entries.length === 0) {
          fetch('/api/state').then(function (r) { return r.json(); })
            .then(function (s) { if (!s.running) _stopConsolePolling(); })
            .catch(function (e) { console.warn('[poll] state fail:', e.message); });
        }
      })
      .catch(function (e) { console.warn('[poll] console fail:', e.message); });
  }

  // ── NestDB を Wren API に差し替え ────────────────────────
  window.NestDB = {
    // main.js が DOMContentLoaded で init().then() を呼ぶため Promise を返す
    init: function () { return Promise.resolve(); },
    save: function (proj) {
      var url    = proj.id ? ('/api/projects/' + proj.id) : '/api/projects';
      var method = proj.id ? 'PUT' : 'POST';
      return fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(proj),
      }).then(function (r) { return r.json(); });
    },
    getAll:  function () { return fetch('/api/projects').then(function (r) { return r.json(); }); },
    getById: function (id) {
      return fetch('/api/projects/' + id).then(function (r) {
        return r.status === 404 ? null : r.json();
      });
    },
    remove:  function (id) {
      return fetch('/api/projects/' + id, { method: 'DELETE' }).then(function (r) { return r.json(); });
    },
    count:   function () { return window.NestDB.getAll().then(function (l) { return l.length; }); },
  };

  // ── getToolboxConfig を上書き ─────────────────────────────
  // nestcore + gamepad を常時有効化し、「拡張機能」ダミーカテゴリを除去する。
  var _origGetToolboxConfig = null;
  function _patchToolbox() {
    if (typeof getToolboxConfig !== 'function') return;
    _origGetToolboxConfig = getToolboxConfig;
    window.getToolboxConfig = function (boardType) {
      // nestcore と gamepad のブロック定義が確実に初期化されるよう有効化
      if (typeof NestPlugins !== 'undefined') {
        ['nestcore', 'gamepad'].forEach(function (id) {
          if (!NestPlugins.isEnabled(id)) NestPlugins.enable(id);
        });
      }
      var toolbox = _origGetToolboxConfig(boardType || 'pico');
      // 「拡張機能」カテゴリと直前の sep を除去
      toolbox.contents = toolbox.contents.filter(function (c) {
        return !(c.kind === 'category' && c.name === '拡張機能');
      });
      // 末尾の連続 sep を除去
      while (toolbox.contents.length > 0 &&
             toolbox.contents[toolbox.contents.length - 1].kind === 'sep') {
        toolbox.contents.pop();
      }
      return toolbox;
    };
  }

  // ── 接続 UI ───────────────────────────────────────────────
  window.updateConnectionUI = function (connected) {
    var btn   = document.getElementById('connectBtn');
    var label = document.getElementById('connectLabel');
    if (!btn || !label) return;
    if (connected) {
      btn.classList.add('connected');
      label.textContent = 'Wren 接続済み';
    } else {
      btn.classList.remove('connected');
      label.textContent = 'Wren 未接続';
    }
  };

  window.toggleConnection = function () {
    if (NestSerial.isConnected()) {
      NestSerial.disconnect().then(function () {
        updateConnectionUI(false);
        _stopConsolePolling();
        logToConsole('Wren から切断しました', 'warn');
      });
    } else {
      NestSerial.connect().then(function (info) {
        updateConnectionUI(true);
        logToConsole('Wren に接続しました (v' + info.version + ')', 'ok');
      }).catch(function (err) {
        logToConsole('接続エラー: ' + err.message, 'err');
        toast('Wren への接続に失敗しました');
      });
    }
  };

  // ── async→sync 変換 ──────────────────────────────────────
  // core1 では asyncio ループを起動できないため、
  // uasyncio ベースの生成コードを同期 (time.sleep) ベースに変換する。
  function _asyncToSync(code) {
    var out = code;
    // import uasyncio → import time (すでに import time があれば削除するだけ)
    out = out.replace(/^([ \t]*)import uasyncio[ \t]*$/mg, '$1import time');
    // async def → def
    out = out.replace(/^([ \t]*)async def /mg, '$1def ');
    // await uasyncio.sleep( → time.sleep(
    out = out.replace(/\bawait uasyncio\.sleep\b/g, 'time.sleep');
    // await uasyncio.sleep_ms( → time.sleep_ms(
    out = out.replace(/\bawait uasyncio\.sleep_ms\b/g, 'time.sleep_ms');
    // uasyncio.run(main()) → main()
    out = out.replace(/^uasyncio\.run\(main\(\)\)[ \t]*$/mg, 'main()');
    // await uasyncio.gather(task_0(), task_1(), ...) → 順次呼び出し
    out = out.replace(/^([ \t]*)await uasyncio\.gather\((.*)\)[ \t]*$/mg,
      function(_m, indent, args) {
        return args.split(',').map(function(t) {
          return indent + t.trim();
        }).join('\n');
      }
    );
    // 残った await キーワードを除去
    out = out.replace(/\bawait /g, '');
    return out;
  }

  // ── runCode ───────────────────────────────────────────────
  window.runCode = function () {
    var panel = document.getElementById('bottomPanel');
    if (panel) panel.classList.remove('collapsed');
    var out = document.getElementById('consoleOutput');
    if (out) out.innerHTML = '';

    var code;
    try {
      if (!window.blocklyWorkspace) { toast('ワークスペースが準備できていません'); return; }
      code = generateCode ? generateCode() : '';
      if (!code || !code.trim()) { toast('実行するコードがありません'); return; }
    } catch (e) {
      logToConsole('コード生成エラー: ' + e.message, 'err');
      toast('コード生成エラー: ' + e.message);
      return;
    }

    if (window.blocklyWorkspace) Blockly.svgResize(window.blocklyWorkspace);
    console.log('[Wren] runCode: コード送信 (' + code.length + ' chars)');
    console.log('[Wren] コード先頭:\n' + code.split('\n').slice(0, 6).join('\n'));
    logToConsole('▶ 送信中...', 'ok');

    fetch('/api/program', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: code }),
    })
      .then(function (r) {
        console.log('[Wren] /api/program 応答:', r.status);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return fetch('/api/run', { method: 'POST' });
      })
      .then(function (r) {
        console.log('[Wren] /api/run 応答:', r.status);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (json) {
        console.log('[Wren] /api/run 結果:', JSON.stringify(json));
        logToConsole('[Wren] 実行中...', 'ok');
        _startConsolePolling();
      })
      .catch(function (err) {
        console.error('[Wren] 実行エラー:', err.message);
        logToConsole('実行エラー: ' + err.message, 'err');
        toast('実行エラー: ' + err.message);
      });
  };

  // ── stopExec ──────────────────────────────────────────────
  window.stopExec = function () {
    fetch('/api/stop', { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function () {
        logToConsole('■ 停止しました', 'warn');
        _stopConsolePolling();
      })
      .catch(function (err) {
        logToConsole('停止エラー: ' + err.message, 'err');
      });
  };

  // ── uploadCode: 書き込みのみ (RUN モード切替はピンで制御) ─
  var _wmTimer = null;

  function _wmEl(id) { return document.getElementById(id); }

  function _wmSetProgress(pct, totalBytes) {
    var p = Math.min(Math.round(pct), 100);
    _wmEl('wmFill')  && (_wmEl('wmFill').style.width   = p + '%');
    _wmEl('wmPct')   && (_wmEl('wmPct').textContent    = p + '%');
    if (_wmEl('wmBytes') && totalBytes != null) {
      var sent = Math.round(totalBytes * p / 100);
      _wmEl('wmBytes').textContent = sent + ' B / ' + totalBytes + ' B';
    }
  }

  function _wmShow(id)  { var el = _wmEl(id); if (el) el.style.display = 'block'; }
  function _wmHide(id)  { var el = _wmEl(id); if (el) el.style.display = 'none';  }

  function _wmOpen(byteCount) {
    var ov = _wmEl('wmOverlay');
    if (!ov) { logToConsole('書き込み中...', 'warn'); return; }

    _wmEl('wmTitle')  && (_wmEl('wmTitle').textContent  = '書き込み中…');
    _wmEl('wmStatus') && (_wmEl('wmStatus').textContent = 'プログラムを送信中…');
    _wmEl('wmRate')   && (_wmEl('wmRate').textContent   = '— KB/s');
    _wmHide('wmDone');
    _wmShow('wmCancel');
    _wmHide('wmClose');
    _wmSetProgress(0, byteCount);

    ov.style.display = 'flex';
    ov.classList.add('show');

    // 模擬プログレス: 指数的に 80% まで近づく
    clearInterval(_wmTimer);
    var _start = Date.now();
    _wmTimer = setInterval(function () {
      var p = 80 * (1 - Math.exp(-(Date.now() - _start) / 700));
      _wmSetProgress(p, byteCount);
    }, 50);
  }

  function _wmFinish() {
    clearInterval(_wmTimer);
    _wmSetProgress(100);
    _wmEl('wmTitle')  && (_wmEl('wmTitle').textContent  = '書き込み完了！');
    _wmEl('wmStatus') && (_wmEl('wmStatus').textContent = '書き込みが完了しました');
    _wmShow('wmDone');
    _wmHide('wmCancel');
    _wmShow('wmClose');
  }

  function _wmFail(msg) {
    clearInterval(_wmTimer);
    _wmEl('wmTitle')  && (_wmEl('wmTitle').textContent  = '書き込み失敗');
    _wmEl('wmStatus') && (_wmEl('wmStatus').textContent = 'エラー: ' + (msg || '不明なエラー'));
    _wmHide('wmCancel');
    _wmShow('wmClose');
  }

  window.closeWriteModal = function () {
    clearInterval(_wmTimer);
    var ov = _wmEl('wmOverlay');
    if (ov) {
      ov.classList.remove('show');
      ov.style.display = 'none';
    }
  };

  window.uploadCode = function () {
    if (!window.blocklyWorkspace) { toast('コードがありません'); return; }
    var code = generateCode();
    if (!code.trim()) { toast('書き込むコードがありません'); return; }

    var byteCount = (new TextEncoder().encode(code)).length;
    _wmOpen(byteCount);

    NestSerial.uploadCode(code)
      .then(function () {
        return NestSerial.switchToRunMode();
      })
      .then(function () {
        _wmFinish();
        logToConsole('書き込み完了 — RUN モードで再起動します', 'ok');
      })
      .catch(function (err) {
        _wmFail(err.message);
        logToConsole('書き込みエラー: ' + err.message, 'err');
        toast('書き込みに失敗しました');
      });
  };

  // ── ツールバーに「XML読込」ボタンを注入 ──────────────────
  function _injectXmlButton() {
    // ダウンロードボタンと同じグループ (.wsg) を探す
    var downloadBtn = document.querySelector('button[onclick="downloadProject()"]');
    if (!downloadBtn) return;

    var btn = document.createElement('button');
    btn.className = 'wsb';
    btn.title = 'XML を読み込む';
    btn.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M3 15v4a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4"/>' +
        '<polyline points="17 9 12 4 7 9"/>' +
        '<line x1="12" y1="4" x2="12" y2="15"/>' +
      '</svg>';
    btn.addEventListener('click', function () { openFileProject(); });

    // ダウンロードボタンの前に挿入
    downloadBtn.parentNode.insertBefore(btn, downloadBtn);
  }

  // ── Blockly.inject に media オプションを強制設定 ──────────
  // sprites.png を data:URI として埋め込み、Zoom/Trash アイコンを修復する
  var _SPRITES_URI = 'data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiIHN0YW5kYWxvbmU9Im5vIj8+CjxzdmcgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIiB2ZXJzaW9uPSIxLjEiIHdpZHRoPSI5NnB4IiBoZWlnaHQ9IjEyNHB4Ij4KICA8c3R5bGUgdHlwZT0idGV4dC9jc3MiPgojYmFja2dyb3VuZCB7CiAgZmlsbDogbm9uZTsKfQouYXJyb3dzIHsKICBmaWxsOiAjMDAwOwogIHN0cm9rZTogbm9uZTsKfQouc2VsZWN0ZWQ+LmFycm93cyB7CiAgZmlsbDogI2ZmZjsKfQouY2hlY2ttYXJrIHsKICBmaWxsOiAjMDAwOwogIGZvbnQtZmFtaWx5OiBzYW5zLXNlcmlmOwogIGZvbnQtc2l6ZTogMTBwdDsKICB0ZXh0LWFuY2hvcjogbWlkZGxlOwp9Ci50cmFzaCB7CiAgZmlsbDogIzg4ODsKfQouem9vbSB7CiAgZmlsbDogbm9uZTsKICBzdHJva2U6ICM4ODg7CiAgc3Ryb2tlLXdpZHRoOiAyOwogIHN0cm9rZS1saW5lY2FwOiByb3VuZDsKfQouem9vbT4uY2VudGVyIHsKICBmaWxsOiAjODg4OwogIHN0cm9rZS13aWR0aDogMDsKfQogIDwvc3R5bGU+CiAgPHJlY3QgaWQ9ImJhY2tncm91bmQiIHdpZHRoPSI5NiIgaGVpZ2h0PSIxMjQiIHg9IjAiIHk9IjAiIC8+CgogIDxnPgogICAgPHBhdGggY2xhc3M9ImFycm93cyIgZD0iTSAxMywxLjUgMTMsMTQuNSAxLjc0LDggeiIgLz4KICAgIDxwYXRoIGNsYXNzPSJhcnJvd3MiIGQ9Ik0gMTcuNSwzIDMwLjUsMyAyNCwxNC4yNiB6IiAvPgogICAgPHBhdGggY2xhc3M9ImFycm93cyIgZD0iTSAzNSwxLjUgMzUsMTQuNSA0Ni4yNiw4IHoiIC8+CiAgPC9nPgogIDxnIGNsYXNzPSJzZWxlY3RlZCIgdHJhbnNmb3JtPSJ0cmFuc2xhdGUoMCwgMTYpIj4KICAgIDxwYXRoIGNsYXNzPSJhcnJvd3MiIGQ9Ik0gMTMsMS41IDEzLDE0LjUgMS43NCw4IHoiIC8+CiAgICA8cGF0aCBjbGFzcz0iYXJyb3dzIiBkPSJNIDE3LjUsMyAzMC41LDMgMjQsMTQuMjYgeiIgLz4KICAgIDxwYXRoIGNsYXNzPSJhcnJvd3MiIGQ9Ik0gMzUsMS41IDM1LDE0LjUgNDYuMjYsOCB6IiAvPgogIDwvZz4KCiAgPHRleHQgY2xhc3M9ImNoZWNrbWFyayIgeD0iNTUuNSIgeT0iMjgiPiYjMTAwMDM7PC90ZXh0PgoKICA8ZyBjbGFzcz0idHJhc2giPgogICAgPHBhdGggZD0iTSAyLDQxIHYgNiBoIDQyIHYgLTYgaCAtMTAuNSBsIC0zLC0zIGggLTE1IGwgLTMsMyB6IiAvPgogICAgPHJlY3Qgd2lkdGg9IjM2IiBoZWlnaHQ9IjIwIiB4PSI1IiB5PSI1MCIgLz4KICAgIDxyZWN0IHdpZHRoPSIzNiIgaGVpZ2h0PSI0MiIgeD0iNSIgeT0iNTAiIHJ4PSI0IiByeT0iNCIgLz4KICA8L2c+CgogIDxnIGNsYXNzPSJ6b29tIj4KICAgIDxjaXJjbGUgcj0iMTEuNSIgY3g9IjE2IiBjeT0iMTA4IiAvPgogICAgPGNpcmNsZSByPSI0LjMiIGN4PSIxNiIgY3k9IjEwOCIgY2xhc3M9ImNlbnRlciIgLz4KICAgIDxwYXRoIGQ9Im0gMjgsMTA4IGgzIiAvPgogICAgPHBhdGggZD0ibSAxLDEwOCBoMyIgLz4KICAgIDxwYXRoIGQ9Im0gMTYsMTIwIHYzIiAvPgogICAgPHBhdGggZD0ibSAxNiw5MyB2MyIgLz4KICA8L2c+CgogIDxnIGNsYXNzPSJ6b29tIj4KICAgIDxjaXJjbGUgcj0iMTUiIGN4PSI0OCIgY3k9IjEwOCIgLz4KICAgIDxwYXRoIGQ9Im0gNDgsMTAxLjYgdjEyLjgiIC8+CiAgICA8cGF0aCBkPSJtIDQxLjYsMTA4IGgxMi44IiAvPgogIDwvZz4KCiAgPGcgY2xhc3M9Inpvb20iPgogICAgPGNpcmNsZSByPSIxNSIgY3g9IjgwIiBjeT0iMTA4IiAvPgogICAgPHBhdGggZD0ibSA3My42LDEwOCBoMTIuOCIgLz4KICA8L2c+Cjwvc3ZnPgo=';

  function _fixBlocklySprites() {
    var XLINK = 'http://www.w3.org/1999/xlink';
    var imgs = document.querySelectorAll('image');
    for (var i = 0; i < imgs.length; i++) {
      var href = imgs[i].getAttributeNS(XLINK, 'href') || imgs[i].getAttribute('href') || '';
      if (href.indexOf('sprites') !== -1 || href.indexOf('data:image/gif') !== -1) {
        imgs[i].setAttributeNS(XLINK, 'href', _SPRITES_URI);
        imgs[i].setAttribute('href', _SPRITES_URI);
      }
    }
  }

  (function () {
    if (typeof Blockly === 'undefined') return;
    var _orig = Blockly.inject.bind(Blockly);
    Blockly.inject = function (container, options) {
      options = Object.assign({}, options);
      // 1×1 GIF で cursor/sound などの余分な 404 を抑制
      options.media = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7/';
      var ws = _orig(container, options);
      // sprites.png 参照を SVG data:URI で上書きして Zoom/Trash アイコンを修復
      requestAnimationFrame(_fixBlocklySprites);
      return ws;
    };
  })();

  // ── ファイル保存ヘルパー ──────────────────────────────────────
  // Pico の /api/export エンドポイントを経由してダウンロードする。
  // HTTP の Content-Disposition: attachment ヘッダーは iOS Safari でも
  // 確実にファイル保存を行うため、blob URL 方式より信頼性が高い。
  function _saveFile(text, filename, callback) {
    fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: filename, data: text }),
    })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        // window.location.href → Content-Disposition: attachment で
        // ブラウザがファイルとして保存し、ページは遷移しない
        window.location.href = '/api/export';
        if (callback) callback();
      })
      .catch(function (e) {
        console.warn('[Wren] /api/export failed, using blob fallback:', e.message);
        // Pico 未接続時フォールバック (デスクトップブラウザのみ動作)
        var blob = new Blob([text], { type: 'application/octet-stream' });
        var url  = URL.createObjectURL(blob);
        var a    = document.createElement('a');
        a.href     = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
        if (callback) callback();
      });
  }

  // ── downloadProject を上書き ──────────────────────────────────
  window.downloadProject = function () {
    if (!currentProject || !window.blocklyWorkspace) {
      toast('ダウンロードするプロジェクトがありません');
      return;
    }
    var xml = Blockly.Xml.workspaceToDom(window.blocklyWorkspace);
    xml.setAttribute('data-board', currentProject.boardType || 'pico');
    var enabledPlugins = (currentProject.plugins || []).join(',');
    if (enabledPlugins) xml.setAttribute('data-plugins', enabledPlugins);
    var xmlText = Blockly.Xml.domToText(xml);
    var name = currentProject.name || 'project';
    _openProjectDownload(xmlText, name);
  };

  function _openProjectDownload(xmlText, name) {
    var existing = document.getElementById('wrenDownloadDialog');
    if (existing) return;
    var previousFocus = document.activeElement;
    var dialog = document.createElement('dialog');
    dialog.id = 'wrenDownloadDialog';
    dialog.className = 'dialog wren-download-dialog';
    dialog.setAttribute('aria-labelledby', 'wrenDownloadTitle');
    dialog.innerHTML =
      '<form>' +
      '<div class="dialog-title" id="wrenDownloadTitle" tabindex="-1" autofocus>プロジェクトをダウンロード</div>' +
      '<label class="dialog-label" for="wrenDownloadName">ファイル名</label>' +
      '<input class="dialog-input" id="wrenDownloadName" type="text" maxlength="100" autocomplete="off" required aria-describedby="wrenDownloadHint">' +
      '<div class="dialog-msg" id="wrenDownloadHint">拡張子 .xml は自動で付きます。</div>' +
      '<div class="dialog-btns">' +
      '<button class="dbtn" type="button">キャンセル</button>' +
      '<button class="dbtn dbtn-fill" type="submit">保存</button>' +
      '</div></form>';
    var scrollX = window.scrollX;
    var scrollY = window.scrollY;
    document.body.classList.add('wren-download-open');
    document.body.appendChild(dialog);
    var input = dialog.querySelector('input');
    input.value = name.replace(/\.xml$/i, '');
    dialog.querySelector('button[type="button"]').addEventListener('click', function () {
      dialog.close();
    });
    dialog.addEventListener('close', function () {
      dialog.remove();
      document.body.classList.remove('wren-download-open');
      if (previousFocus && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
      window.scrollTo(scrollX, scrollY);
    });
    input.addEventListener('input', function () { input.setCustomValidity(''); });
    dialog.querySelector('form').addEventListener('submit', function (event) {
      event.preventDefault();
      var filename = input.value.trim().replace(/(?:\.xml)+$/i, '').trim();
      if (!filename || /[<>:"/\\|?*\x00-\x1f\x7f]/.test(filename) || /[. ]$/.test(filename)) {
        input.setCustomValidity('ファイル名を入力してください。末尾のピリオドや、\\ / : * ? " < > | は使えません。');
        input.reportValidity();
        return;
      }
      dialog.close();
      _saveFile(xmlText, filename + '.xml', function () {
        toast('「' + filename + '」を保存しました');
      });
    });
    dialog.showModal();
    // タッチ端末では自動でキーボードを開かず、画面の押し上げを防ぐ。
    if (window.matchMedia('(pointer: fine)').matches) {
      input.focus({ preventScroll: true });
      input.select();
    } else {
      dialog.querySelector('.dialog-title').focus({ preventScroll: true });
    }
  }

  // ── downloadCode を上書き ─────────────────────────────────────
  window.downloadCode = function () {
    if (!window.blocklyWorkspace) return;
    var code = generateCode();
    if (!code.trim()) return;
    _saveFile(code, 'main.py', function () {
      toast('コードをダウンロードしました');
    });
  };

  // ── Chart / home 画面 スタブ (main.js が呼ぶが Wren では不要) ─
  window.resetChart        = function () {};
  window.updateChart       = function () {};
  window.addChartData      = function () {};
  window._chartInstances   = {};
  window.renderProjectGrid = function () {};
  window.updateStorageInfo = function () {};

  // ── 起動時処理 ────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', function () {
    // デフォルトプロジェクト設定 (currentProject が null だと各所でエラー)
    if (!window.currentProject) {
      window.currentProject = {
        id: null,
        name: 'Wren',
        boardType: 'pico',
        xml: null,
        plugins: ['nestcore', 'gamepad'],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
    }

    // getToolboxConfig をパッチしてからワークスペースを初期化
    _patchToolbox();

    // nestcore + gamepad を有効化 (ブロック定義を登録)
    if (typeof NestPlugins !== 'undefined') {
      ['nestcore', 'gamepad'].forEach(function (id) {
        if (!NestPlugins.isEnabled(id)) NestPlugins.enable(id);
      });
    }

    // ワークスペースタブへ直接遷移 (initBlockly が呼ばれる)
    switchTab('workspace');
    // showWorkspace() で空状態を非表示 & ボード別ツールボックス適用
    showWorkspace();

    // コンソールを開く
    var panel = document.getElementById('bottomPanel');
    if (panel) panel.classList.remove('collapsed');

    // XML読込ボタンを注入
    _injectXmlButton();

    // Wren に自動接続
    NestSerial.connect().then(function (info) {
      updateConnectionUI(true);
      logToConsole('Wren 接続 — ' + info.ssid + ' v' + info.version, 'ok');
    }).catch(function () {
      updateConnectionUI(false);
      logToConsole('Wren に接続できませんでした', 'err');
    });
  });

})();
