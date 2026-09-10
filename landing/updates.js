// このブラウザで最後に書き込みが完了した版を記録する。
(function () {
  'use strict';
  var KEY = 'nestblocks-wren:last-installed:v1';
  var release = window.WREN_RELEASE;
  if (!release || typeof release.version !== 'string' || typeof release.build_id !== 'string') return;

  var versionEl = document.getElementById('firmwareVersion');
  var previousEl = document.getElementById('firmwarePrevious');
  var dialog = document.getElementById('firmwareUpdateDialog');
  versionEl.textContent = 'v' + release.version;

  function readPrevious() {
    try {
      var value = JSON.parse(localStorage.getItem(KEY));
      if (value && typeof value.version === 'string' && typeof value.build_id === 'string') return value;
    } catch (e) {
      // 保存が使えない環境でも、インストール操作は妨げない。
    }
    return null;
  }

  function showPrevious(previous) {
    previousEl.textContent = previous
      ? 'このブラウザで前回書き込んだ版：v' + previous.version
      : 'このブラウザには、書き込み完了の記録がありません。';
  }
  showPrevious(readPrevious());

  window.WrenUpdates = {
    recordInstalled: function () {
      try {
        localStorage.setItem(KEY, JSON.stringify({
          version: release.version,
          build_id: release.build_id,
          installed_at: new Date().toISOString(),
        }));
        showPrevious(release);
      } catch (e) {
        previousEl.textContent = '書き込みは完了しましたが、このブラウザに履歴を保存できませんでした。';
      }
      if (dialog.open) dialog.close();
    },
  };

  dialog.querySelector('[data-update-later]').addEventListener('click', function () { dialog.close(); });
  dialog.querySelector('[data-update-setup]').addEventListener('click', function () {
    dialog.close();
    document.getElementById('setup').scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  function checkForUpdate() {
    var previous = readPrevious();
    if (!previous || (previous.version === release.version && previous.build_id === release.build_id)) return;
    document.getElementById('firmwareUpdatePrevious').textContent = 'v' + previous.version;
    document.getElementById('firmwareUpdateLatest').textContent = 'v' + release.version;
    document.getElementById('firmwareUpdateDetail').textContent = previous.version === release.version
      ? 'バージョン番号は同じですが、配布内容が更新されています。'
      : '前回このブラウザで書き込んだ版と、現在配布中の版が異なります。';
    // 接続・書き込み操作が始まっている場合は割り込まない。
    if (document.getElementById('setup-connect-btn').disabled) return;
    if (typeof dialog.showModal === 'function' && !dialog.open) dialog.showModal();
  }
  if (document.readyState === 'complete') setTimeout(checkForUpdate, 1000);
  else window.addEventListener('load', function () { setTimeout(checkForUpdate, 1000); }, { once: true });
})();
