#!/usr/bin/env node
// build-wren.mjs — NestBlocks Wren フロントエンドビルド
//
// 実行: node build/build-wren.mjs
// 出力: firmware/www/index.html
//       firmware/www/app.{HASH}.js.gz
//       firmware/www/app.{HASH}.css.gz
//
// 必要な Node.js バージョン: 18+

import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync, copyFileSync } from 'fs';
import { createHash }  from 'crypto';
import { gzipSync }    from 'zlib';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT  = join(__dir, '..');
const NB    = join(ROOT, '..', 'NestBlocks', 'NestBlocks_V3', 'NestBlocks');
const SRC   = join(ROOT, 'src');
const OUT   = join(ROOT, 'firmware', 'www');
const ORIGIN = JSON.parse(readFileSync(join(__dir, 'wren-origin.json'), 'utf-8'));
const MARKER = `${ORIGIN.project} | Origin-ID: ${ORIGIN.origin_id}`;
const BANNER = `/*! ${MARKER}\n * ${ORIGIN.notice}\n */\n`;

// ── 出力ディレクトリをクリーンアップ ─────────────────────────
mkdirSync(OUT, { recursive: true });
for (const f of readdirSync(OUT)) {
  if (f.endsWith('.gz') || f === 'index.html') rmSync(join(OUT, f));
}

// ── JS バンドル ───────────────────────────────────────────────
// serial.js は WebSerial 専用のため除外。
// Blockly はオフライン動作のため同梱。
// プラグインファイルも同梱 (HTML から個別ロードしていたもの)。
const JS_FILES = [
  // Blockly コア
  join(NB, 'assets', 'blockly_compressed.js'),
  join(NB, 'assets', 'blocks_compressed.js'),
  join(NB, 'assets', 'python_compressed.js'),
  join(NB, 'assets', 'ja.js'),
  // アプリ本体 (DOM 依存コードは body 末尾で実行されるため問題なし)
  join(NB, 'assets', 'js', 'db.js'),
  join(NB, 'assets', 'js', 'i18n.js'),
  join(NB, 'assets', 'js', 'help.js'),
  join(NB, 'assets', 'js', 'plugins.js'),
  join(NB, 'assets', 'js', 'plugins', 'nestcore.js'),
  // robopad.js は外部ネットワーク (QR コード・スプライト) を必要とするため除外
  join(NB, 'assets', 'js', 'plugins', 'gamepad.js'),
  join(NB, 'assets', 'js', 'plugins', 'uart.js'),
  join(NB, 'assets', 'js', 'plugins', 'i2c.js'),
  join(NB, 'assets', 'js', 'toolbox.js'),
  join(NB, 'assets', 'js', 'block_definitions.js'),
  join(NB, 'assets', 'js', 'python_generators.js'),
  join(NB, 'assets', 'js', 'ble_blocks.js'),
  join(NB, 'assets', 'js', 'main.js'),
  join(SRC, 'wren_generators.js'),
  join(SRC, 'wren_api_client.js'),
  join(SRC, 'wren_main_patch.js'),
];

const CSS_FILES = [
  join(NB,  'assets', 'css', 'style.css'),
  join(SRC, 'wren_layout.css'),
];

function readAll(files) {
  return files.map(f => {
    try {
      let src = readFileSync(f, 'utf-8');
      // Wren 独自のファイルだけに付記。第三者ソースの権利表示は変更しない。
      if (dirname(f) === SRC) src = BANNER + src;
      console.log(`  ✓ ${f.split(/[\\/]/).slice(-4).join('/')}`);
      return src;
    } catch (e) {
      console.error(`  ✗ ${f} — ${e.message}`);
      process.exit(1);
    }
  }).join('\n;\n');   // ';' で区切るとファイル末尾の ASI 問題を防ぐ
}

console.log('\n[JS]');
const jsBundle  = readAll(JS_FILES);

console.log('\n[CSS]');
const cssBundle = readAll(CSS_FILES);

// ── コンテンツハッシュ ────────────────────────────────────────
function hash(str) {
  return createHash('sha256').update(str).digest('hex').slice(0, 12);
}

const jsHash  = hash(jsBundle);
const cssHash = hash(cssBundle);
const jsName  = `app.${jsHash}.js`;
const cssName = `app.${cssHash}.css`;

// ── gzip 圧縮 ─────────────────────────────────────────────────
const jsGz  = gzipSync(Buffer.from(jsBundle,  'utf-8'), { level: 9 });
const cssGz = gzipSync(Buffer.from(cssBundle, 'utf-8'), { level: 9 });

writeFileSync(join(OUT, jsName  + '.gz'), jsGz);
writeFileSync(join(OUT, cssName + '.gz'), cssGz);

console.log(`\n[OUT] ${jsName}.gz   (${(jsGz.length / 1024).toFixed(1)} KB)`);
console.log(`[OUT] ${cssName}.gz  (${(cssGz.length / 1024).toFixed(1)} KB)`);

// ── HTML 変換 ─────────────────────────────────────────────────
// ホーム画面アイコンはロゴ原稿の白抜き・オレンジ地版。
for (const size of [180, 192, 512]) {
  copyFileSync(join(SRC, 'icons', `icon-${size}.png`), join(OUT, `icon-${size}.png`));
}
writeFileSync(join(OUT, 'manifest.json'), JSON.stringify({
  name: 'NestBlocks Wren',
  short_name: 'NestBlocks Wren',
  start_url: '/',
  scope: '/',
  display: 'browser',
  icons: [192, 512].map(size => ({
    src: `/icon-${size}.png`, sizes: `${size}x${size}`, type: 'image/png',
  })),
}, null, 2));
let html = readFileSync(join(NB, 'index.html'), 'utf-8');
html = html.replace(/<link\b[^>]*rel="(?:apple-touch-icon|icon|manifest)"[^>]*>\s*/gi, '');
html = html.replace('</head>', [
  '<link rel="apple-touch-icon" sizes="180x180" href="/icon-180.png">',
  '<link rel="icon" type="image/png" sizes="192x192" href="/icon-192.png">',
  '<link rel="manifest" href="/manifest.json">',
  '<meta name="apple-mobile-web-app-title" content="NestBlocks Wren">',
  '</head>',
].join('\n'));

// タイトル
html = html.replace(/<title>NestBlocks<\/title>/, '<title>NestBlocks Wren</title>');

// viewport (iPad 向け)
html = html.replace(
  /content="width=device-width, initial-scale=1\.0"/,
  'content="width=device-width, initial-scale=1.0, maximum-scale=1.0"'
);

// CDN リンクを削除
html = html.replace(/[ \t]*<link[^>]*fonts\.googleapis\.com[^>]*>\n?/g, '');
html = html.replace(/[ \t]*<link[^>]*fonts\.gstatic\.com[^>]*>\n?/g,   '');
html = html.replace(/[ \t]*<script[^>]*prism[^>]*><\/script>\n?/gi,    '');
html = html.replace(/[ \t]*<script[^>]*chart\.js[^>]*><\/script>\n?/gi,'');

// HEAD 内の assets/ スクリプトをすべて削除 (Blockly 4本 + カスタム 3本)
html = html.replace(/[ \t]*<script[^>]*src="assets\/[^"]+"><\/script>\n?/g, '');

// BODY 末尾の assets/js/ スクリプトをすべて削除
// (上の regex で一括削除済みのため追加処理不要)

// style.css → バンドル CSS
html = html.replace(
  /<link\s+rel="stylesheet"\s+href="assets\/css\/style\.css[^"]*">/,
  `<link rel="stylesheet" href="/${cssName}">`
);

// ── ホームタブ nav ボタンを削除
html = html.replace(/[ \t]*<button[^>]*data-tab="home"[^>]*>.*?<\/button>\n?/gs, '');
// ── グラフタブ nav ボタンを削除
html = html.replace(/[ \t]*<button[^>]*data-tab="chart"[^>]*>.*?<\/button>\n?/gs, '');

// ── ホームタブパネル (コメントごと) を削除
html = html.replace(
  /[ \t]*<!-- ====== ホーム ====== -->[\s\S]*?(?=[ \t]*<!-- ====== ワークスペース)/,
  '\n\n    '
);
// ── グラフタブパネル (コメントごと) を削除
html = html.replace(
  /[ \t]*<!-- ====== グラフ ====== -->[\s\S]*?(?=[ \t]*<!-- ====== 設定)/,
  '\n\n    '
);

// ── workspace を active にする (home が active だったため移し替え)
html = html.replace(
  /<div class="tab-panel" id="workspace">/,
  '<div class="tab-panel active" id="workspace">'
);
// workspace nav ボタンを active にする
html = html.replace(
  /<button class="nav-item" data-tab="workspace">/,
  '<button class="nav-item active" data-tab="workspace">'
);

// ── RoboPad モーダル全体を削除 (外部 QR コード img を含む)
html = html.replace(/[ \t]*<div[^>]*id="roboPadOverlay"[^>]*>[\s\S]*?<\/div>\s*<\/div>\s*/g, '');

// ── ロゴ onclick を workspace に変更 (home タブは削除済み)
html = html.replace(
  /onclick="switchTab\('home'\)"/,
  'onclick="switchTab(\'workspace\')"'
);

// ── ローディング画面: Wren マーク SVG に差し替え
const WREN_MARK_SVG = [
  '<svg class="ld-logo-svg" viewBox="0 0 66 54" fill="none">',
  '          <rect class="ld-wren-tail" x="38" y="0" width="13" height="30" rx="3.25" fill="var(--orange)" transform="rotate(32 44.5 30)"/>',
  '          <rect class="ld-wren-body-v" x="8" y="8" width="14" height="34" rx="3.5" fill="currentColor"/>',
  '          <rect class="ld-wren-body-h" x="8" y="28" width="34" height="14" rx="3.5" fill="currentColor"/>',
  '          <polygon class="ld-wren-arrow" points="8,13 0,17 8,21" fill="var(--orange)"/>',
  '          <circle class="ld-wren-eye" cx="15" cy="16" r="2.2" fill="var(--bg)"/>',
  '        </svg>',
].join('\n');
html = html.replace(/<svg class="ld-logo-svg"[\s\S]*?<\/svg>/, WREN_MARK_SVG);

// ── ローディング画面: ブランド名に "Wren" を追加
html = html.replace(
  '<h1 class="ld-brand">Nest<em>Blocks</em></h1>',
  '<h1 class="ld-brand">Nest<em>Blocks</em><span class="ld-wren-bar"></span><span class="ld-wren-ed">Wren</span></h1>'
);

// ── ヘッダーロゴ: Wren マーク + テキストに差し替え
const WREN_HEADER_LOGO = [
  '<div class="logo-icon">',
  '        <svg viewBox="0 0 66 54" fill="none">',
  '          <rect x="38" y="0" width="13" height="30" rx="3.25" fill="var(--orange)" transform="rotate(32 44.5 30)"/>',
  '          <rect x="8" y="8" width="14" height="34" rx="3.5" fill="currentColor"/>',
  '          <rect x="8" y="28" width="34" height="14" rx="3.5" fill="currentColor"/>',
  '          <polygon points="8,13 0,17 8,21" fill="var(--orange)"/>',
  '          <circle cx="15" cy="16" r="2.2" fill="var(--bg)"/>',
  '        </svg>',
  '      </div>',
  '      <div class="logo-text">Nest<em>Blocks</em><span class="logo-wren-bar"></span><span class="logo-wren-ed">Wren</span></div>',
].join('\n');
html = html.replace(
  /<div class="logo-icon">[\s\S]*?<\/div>\s*\n\s*<div class="logo-text">Nest<span>Blocks<\/span><\/div>/,
  WREN_HEADER_LOGO
);

// ── バンドル JS を </body> の直前に挿入
html = html.replace(
  /(\s*<!-- ローディング画面の即時消去)/,
  `\n  <script src="/${jsName}"></script>\n$1`
);

writeFileSync(join(OUT, 'index.html'), html, 'utf-8');
console.log(`[OUT] index.html     (${(html.length / 1024).toFixed(1)} KB)`);

// ── firmware.js 生成 (LP 用) ──────────────────────────────────
// ソース変更が LP 経由の Pico 書き込みに反映されるよう毎回再生成する。
console.log('\n[firmware.js]');

const FW_DIR  = join(ROOT, 'firmware');
const FW_OUT  = join(ROOT, 'landing', 'firmware.js');
const BIN_CHUNK = 1000;  // Pico REPL が一度に受け取れる base64 チャンクサイズ
const versionMatch = readFileSync(join(FW_DIR, 'wren', 'config.py'), 'utf-8')
  .match(/^VERSION\s*=\s*['"]([^'"]+)['"]/m);
if (!versionMatch) throw new Error('Firmware VERSION is missing');

// ── Python ファームウェアファイルを収集 ───────────────────────
const fwFiles = [
  ['/boot.py',     join(FW_DIR, 'boot.py')],
  ['/main.py',     join(FW_DIR, 'main.py')],
  ['/run_mode.py', join(FW_DIR, 'run_mode.py')],
];
import { readdirSync as _ls } from 'fs';
for (const f of _ls(join(FW_DIR, 'wren')).sort()) {
  if (f.endsWith('.py')) fwFiles.push([`/wren/${f}`, join(FW_DIR, 'wren', f)]);
}

const fwEntries = fwFiles.map(([picoPath, localPath]) => {
  const content = readFileSync(localPath, 'utf-8');
  if (!content.includes(MARKER)) throw new Error(`Missing origin marker: ${localPath}`);
  console.log(`  ✓ ${picoPath}`);
  return `  ${JSON.stringify(picoPath)}: ${JSON.stringify(content)}`;
});

// ビルドごとの照合記録。設定・利用者のプログラム・保存プロジェクトは対象外。
const fileHashes = {};
for (const [picoPath, localPath] of fwFiles) {
  if (picoPath !== '/wren/config.py') {
    fileHashes[picoPath] = createHash('sha256').update(readFileSync(localPath)).digest('hex');
  }
}
for (const fname of _ls(OUT).sort()) {
  if (fname !== 'wren-provenance.json') {
    fileHashes[`/www/${fname}`] = createHash('sha256').update(readFileSync(join(OUT, fname))).digest('hex');
  }
}
const provenance = {
  schema: 1,
  ...ORIGIN,
  build_id: createHash('sha256').update(JSON.stringify(fileHashes)).digest('hex'),
  algorithm: 'sha256',
  excluded: ['/wren/config.py', '/user_program.py', '/projects', '/lib', '/mode.txt', '/export.tmp'],
  files: fileHashes,
};
const provenanceText = JSON.stringify(provenance, null, 2) + '\n';
writeFileSync(join(OUT, 'wren-provenance.json'), provenanceText);
const referenceDir = join(ROOT, 'private-watermark', 'provenance');
mkdirSync(referenceDir, { recursive: true });
writeFileSync(join(referenceDir, provenance.build_id + '.json'), provenanceText);
console.log(`[Origin] ${ORIGIN.origin_id}\n[Build] ${provenance.build_id}`);

// ── www ファイルを収集 ────────────────────────────────────────
const wwwEntries = [];
for (const fname of _ls(join(FW_DIR, 'www')).sort()) {
  const localPath = join(FW_DIR, 'www', fname);
  const picoPath  = `/www/${fname}`;
  if (fname.endsWith('.gz') || fname.endsWith('.png')) {
    const b64    = readFileSync(localPath).toString('base64');
    const chunks = [];
    for (let i = 0; i < b64.length; i += BIN_CHUNK) chunks.push(b64.slice(i, i + BIN_CHUNK));
    console.log(`  ✓ ${picoPath}  (${chunks.length} chunks)`);
    wwwEntries.push(
      `  { path: ${JSON.stringify(picoPath)}, chunks: [\n` +
      chunks.map(c => `    '${c}'`).join(',\n') +
      `\n  ] }`
    );
  } else {
    const content = readFileSync(localPath, 'utf-8');
    console.log(`  ✓ ${picoPath}`);
    wwwEntries.push(`  { path: ${JSON.stringify(picoPath)}, text: ${JSON.stringify(content)} }`);
  }
}

const fwJs = [
  '// firmware.js — auto-generated. Do not edit manually.',
  `var WREN_RELEASE = ${JSON.stringify({ version: versionMatch[1], build_id: provenance.build_id })};`,
  `var FIRMWARE = {\n${fwEntries.join(',\n')},\n};`,
  `var WWW_FILES = [\n${wwwEntries.join(',\n')},\n];`,
].join('\n');

writeFileSync(FW_OUT, fwJs, 'utf-8');
console.log(`[OUT] landing/firmware.js  (${(fwJs.length / 1024).toFixed(1)} KB)`);
// 配布内容が変わったときに、古い JS キャッシュを再利用しない。
const landingPath = join(ROOT, 'landing', 'index.html');
let landingHtml = readFileSync(landingPath, 'utf-8');
for (const [name, content] of [
  ['firmware.js', fwJs],
  ['updates.js', readFileSync(join(ROOT, 'landing', 'updates.js'), 'utf-8')],
]) {
  landingHtml = landingHtml.replace(
    new RegExp(`src="${name.replace('.', '\\.')}[^"/]*"`),
    `src="${name}?v=${hash(content)}"`
  );
}
writeFileSync(landingPath, landingHtml, 'utf-8');

// ── 完了レポート ──────────────────────────────────────────────
const totalKB = ((jsGz.length + cssGz.length) / 1024).toFixed(1);
console.log(`\n✅  ビルド完了 — 合計 ${totalKB} KB (gzip済み)`);
console.log(`   JS  ハッシュ: ${jsHash}`);
console.log(`   CSS ハッシュ: ${cssHash}`);
console.log(`   出力先: ${OUT}\n`);
