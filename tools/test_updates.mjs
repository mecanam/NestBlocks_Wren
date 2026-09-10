// node tools/test_updates.mjs
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = readFileSync(new URL('../landing/updates.js', import.meta.url), 'utf8');
const key = 'nestblocks-wren:last-installed:v1';
const release = { version: '1.4.0', build_id: 'current' };
function page(saved = null, options = {}) {
  const nodes = {};
  const timers = [];
  const storage = new Map(saved === null ? [] : [[key, typeof saved === 'string' ? saved : JSON.stringify(saved)]]);
  function element(id) {
    if (!nodes[id]) nodes[id] = {
      textContent: '', open: false, disabled: false, events: {},
      addEventListener(name, fn) { this.events[name] = fn; },
      querySelector(selector) { return element(selector); },
      showModal() { this.open = true; },
      close() { this.open = false; },
      scrollIntoView() { this.scrolled = true; },
    };
    return nodes[id];
  }
  const context = {
    WREN_RELEASE: release,
    document: { readyState: 'complete', getElementById: element },
    localStorage: {
      getItem(k) { if (options.storageBlocked) throw new Error('blocked'); return storage.get(k) ?? null; },
      setItem(k, v) { if (options.storageBlocked) throw new Error('blocked'); storage.set(k, v); },
    },
    setTimeout: fn => timers.push(fn),
  };
  context.window = context;
  vm.runInNewContext(source, context);
  if (options.busy) element('setup-connect-btn').disabled = true;
  timers.forEach(fn => fn());
  return { context, storage, element, dialog: element('firmwareUpdateDialog') };
}

assert.equal(page().dialog.open, false, 'first visit');
assert.equal(page(release).dialog.open, false, 'same release');
assert.equal(page({ version: '1.3.0', build_id: 'old' }).dialog.open, true, 'different version');
const changed = page({ version: '1.4.0', build_id: 'old' });
assert.equal(changed.dialog.open, true, 'same version, updated files');
assert(changed.element('firmwareUpdateDetail').textContent.includes('配布内容'));
changed.element('[data-update-later]').events.click();
assert.equal(changed.dialog.open, false);
assert.equal(JSON.parse(changed.storage.get(key)).build_id, 'old', 'dismissal must not mark installed');
changed.context.WrenUpdates.recordInstalled();
assert.equal(JSON.parse(changed.storage.get(key)).build_id, 'current');
assert.equal(page(JSON.parse(changed.storage.get(key))).dialog.open, false, 'next visit after install');
const updating = page({ version: '1.3.0', build_id: 'old' });
updating.element('[data-update-setup]').events.click();
assert.equal(updating.element('setup').scrolled, true);
assert.equal(JSON.parse(updating.storage.get(key)).build_id, 'old', 'opening setup must not mark installed');
assert.equal(page('not json').dialog.open, false);
assert.equal(page({ version: 12 }).dialog.open, false);
assert.equal(page({ version: '1.3.0', build_id: 'old' }, { busy: true }).dialog.open, false);
const blocked = page(null, { storageBlocked: true });
blocked.context.WrenUpdates.recordInstalled();
assert(blocked.element('firmwarePrevious').textContent.includes('保存できません'));
console.log('Update notification, persistent history, dismissal, setup navigation and storage failures: OK');
