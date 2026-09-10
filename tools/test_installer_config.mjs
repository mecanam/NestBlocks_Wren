// node tools/test_installer_config.mjs
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const html = readFileSync(new URL('../landing/index.html', import.meta.url), 'utf8');
const source = html.match(/  function _configMatches\(actual, expected\) \{[\s\S]*?\n  \}/)?.[0];
assert.ok(source, 'installer comparison exists');
const context = vm.createContext({});
vm.runInContext(source, context);
const matches = context._configMatches;
const config = "# Origin-ID: test\nSSID='Wren01'\nPASSWORD='wren0001'\nVERSION='1.4.0'\n";
assert.ok(matches(config, config));
assert.ok(matches(config.replace(/\n/g, '\r\n'), config), 'serial CRLF');
const mixed = config.replace('test\n', 'test\r\n');
assert.ok(matches(mixed.replace(/\n/g, '\r\n'), mixed), 'existing CR plus serial CRLF');
assert.ok(matches(config, config.replace(/\n/g, '\r\n')), 'Windows source');
for (const [from, to] of [['Wren01', 'Wren02'], ['wren0001', 'wren0002'], ['1.4.0', '1.3.0']]) {
  assert.equal(matches(config.replace(from, to), config), false, `${from} mismatch`);
}
assert.equal(matches(config.replace("SSID='Wren01'\n", ''), config), false, 'missing setting');
assert.equal(matches(config.replace('Wren01', 'Wren 01'), config), false, 'spaces remain significant');
assert.ok(html.includes('if (!_configMatches(cfg, cfgContent))'), 'installer uses comparison');
for (const [, script] of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
  new vm.Script(script);
}
console.log('Installer config regression checks passed; inline scripts parse.');
