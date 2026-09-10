#!/usr/bin/env bash
# deploy.sh — Wren ファームウェアを Pico W に転送する
#
# 前提条件:
#   - mpremote がインストール済み (pip install mpremote)
#   - Pico W が USB 接続されている
#   - node build/build-wren.mjs を先に実行してある
#
# 使い方:
#   bash build/deploy.sh          # フルデプロイ
#   bash build/deploy.sh --fw     # ファームウェアのみ (www/ 除く)
#   bash build/deploy.sh --www    # www/ のみ

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FW="$ROOT/firmware"

MODE="${1:-}"

# ── ヘルパー ─────────────────────────────────────────────────
log()  { echo "▶ $*"; }
ok()   { echo "✓ $*"; }
fail() { echo "✗ $*" >&2; exit 1; }

# mpremote の存在確認
command -v mpremote &>/dev/null || fail "mpremote が見つかりません: pip install mpremote"

# ── /wren パッケージをアップロード ───────────────────────────
upload_fw() {
  log "ファームウェアをアップロード中..."

  # ルートファイル
  for f in boot.py main.py run_mode.py; do
    if [ -f "$FW/$f" ]; then
      log "  $f"
      mpremote cp "$FW/$f" ":/$f"
    fi
  done

  # /wren ディレクトリを作成
  mpremote exec "import os; os.mkdir('/wren')" 2>/dev/null || true

  # wren パッケージ内ファイル
  for f in "$FW/wren/"*.py; do
    fname="$(basename "$f")"
    log "  wren/$fname"
    mpremote cp "$f" ":/wren/$fname"
  done

  ok "ファームウェア転送完了"
}

# ── /www 以下をアップロード ───────────────────────────────────
upload_www() {
  log "フロントエンドをアップロード中..."

  # /www ディレクトリを作成
  mpremote exec "import os; os.mkdir('/www')" 2>/dev/null || true

  # 古いアセットを削除 (ハッシュ付きファイルを入れ替えるため)
  mpremote exec "
import os
try:
    for f in os.listdir('/www'):
        if f.endswith('.gz') or f == 'index.html':
            os.remove('/www/' + f)
except: pass
" 2>/dev/null || true

  # 新しいアセットを転送
  for f in "$ROOT/firmware/www/"*; do
    fname="$(basename "$f")"
    log "  www/$fname"
    mpremote cp "$f" ":/www/$fname"
  done

  ok "フロントエンド転送完了"
}

# ── /projects ディレクトリ確認 ────────────────────────────────
ensure_projects() {
  mpremote exec "
import os
try:
    os.mkdir('/projects')
except OSError:
    pass
" 2>/dev/null || true
}

# ── メイン ───────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════╗"
echo "║  NestBlocks Wren デプロイツール  ║"
echo "╚══════════════════════════════════╝"
echo ""

# www/ が存在するか確認
if [ "$MODE" != "--fw" ] && [ ! -d "$ROOT/firmware/www" ]; then
  fail "firmware/www/ が見つかりません。先に 'node build/build-wren.mjs' を実行してください"
fi

case "$MODE" in
  --fw)
    upload_fw
    ;;
  --www)
    upload_www
    ;;
  *)
    upload_fw
    upload_www
    ensure_projects
    ;;
esac

# リセット
log "Pico W を再起動中..."
mpremote reset

echo ""
echo "✅  デプロイ完了!"
echo "   Pico W の起動後、Wi-Fi '$( \
  grep -oP "(?<=SSID\s{5}= f').*(?=')" "$FW/wren/config.py" 2>/dev/null \
  || echo "Wren-XX")' に接続して"
echo "   http://192.168.4.1/ にアクセスしてください"
echo ""
