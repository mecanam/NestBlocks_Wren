// ──────────────────────────────────────────────────────────────
// Wren ループジェネレーター — _nb.check() 注入
//
// python_generators.js の後に読み込み、ループ 4 種を上書きする。
// これが既存コードジェネレーターへの唯一の変更点（仕様書 §6.3）。
//
// 注入ルール:
//   branch の先頭に "  _nb.check()\n" を挿入する。
//   branch が PASS (pass\n) の場合は check のみで pass は不要。
// ──────────────────────────────────────────────────────────────

(function () {
  var IND = Blockly.Python.INDENT;   // "  "
  var CHECK = IND + '_nb.check()\n';

  function injectCheck(branch) {
    // branch が pass だけの場合は check に差し替える
    if (branch.trim() === 'pass') return CHECK;
    return CHECK + branch;
  }

  // ── 1. controls_repeat_ext  (〇回繰り返す) ──────────────────
  Blockly.Python['controls_repeat_ext'] = function (block) {
    var repeats = Blockly.Python.valueToCode(
        block, 'TIMES', Blockly.Python.ORDER_NONE) || '0';
    var branch = Blockly.Python.statementToCode(block, 'DO');
    branch = Blockly.Python.addLoopTrap(branch, block);
    branch = injectCheck(branch || Blockly.Python.PASS);
    var loopVar = Blockly.Python.nameDB_.getDistinctName(
        'count', Blockly.VARIABLE_CATEGORY_NAME);
    return 'for ' + loopVar + ' in range(' + repeats + '):\n' + branch;
  };

  // ── 2. controls_whileUntil  (〜の間繰り返す / 〜まで繰り返す) ──
  Blockly.Python['controls_whileUntil'] = function (block) {
    var until = block.getFieldValue('MODE') === 'UNTIL';
    var arg = Blockly.Python.valueToCode(
        block, 'BOOL',
        until ? Blockly.Python.ORDER_LOGICAL_NOT : Blockly.Python.ORDER_NONE
    ) || 'False';
    var branch = Blockly.Python.statementToCode(block, 'DO');
    branch = Blockly.Python.addLoopTrap(branch, block);
    branch = injectCheck(branch || Blockly.Python.PASS);
    var cond = until ? 'not ' + arg : arg;
    return 'while ' + cond + ':\n' + branch;
  };

  // ── 3. controls_for  (〇から〇まで繰り返す) ─────────────────
  Blockly.Python['controls_for'] = function (block) {
    var variable0 = Blockly.Python.nameDB_.getName(
        block.getFieldValue('VAR'), Blockly.VARIABLE_CATEGORY_NAME);
    var from_ = Blockly.Python.valueToCode(
        block, 'FROM', Blockly.Python.ORDER_NONE) || '0';
    var to_   = Blockly.Python.valueToCode(
        block, 'TO', Blockly.Python.ORDER_NONE) || '0';
    var by_   = Blockly.Python.valueToCode(
        block, 'BY', Blockly.Python.ORDER_NONE) || '1';
    var branch = Blockly.Python.statementToCode(block, 'DO');
    branch = Blockly.Python.addLoopTrap(branch, block);
    branch = injectCheck(branch || Blockly.Python.PASS);

    var startVar = Blockly.Python.nameDB_.getDistinctName(
        '__start', Blockly.VARIABLE_CATEGORY_NAME);
    var endVar   = Blockly.Python.nameDB_.getDistinctName(
        '__end', Blockly.VARIABLE_CATEGORY_NAME);
    var stepVar  = Blockly.Python.nameDB_.getDistinctName(
        '__step', Blockly.VARIABLE_CATEGORY_NAME);

    return (
      startVar + ' = ' + from_ + '\n' +
      endVar   + ' = ' + to_   + '\n' +
      stepVar  + ' = ' + by_   + '\n' +
      'for ' + variable0 + ' in range(' +
        startVar + ', ' +
        endVar + ' + 1 if ' + stepVar + ' >= 0 else ' + endVar + ' - 1, ' +
        stepVar + '):\n' + branch
    );
  };

  // ── 4. forever_loop  (ずっと実行する) ──────────────────────
  Blockly.Python['forever_loop'] = function (block) {
    var branch = Blockly.Python.statementToCode(block, 'DO');
    var hasSleep = branch.indexOf('uasyncio.sleep') !== -1;
    branch = injectCheck(branch || Blockly.Python.PASS);

    var code = 'while True:\n' + branch;
    if (hasSleep) {
      code += IND + 'await uasyncio.sleep_ms(10)\n';
    } else {
      code += IND + 'await uasyncio.sleep_ms(100)\n';
    }
    return code;
  };

})();

// ──────────────────────────────────────────────────────────────
// 期待出力サンプル (コードレビュー用コメント)
//
// [forever_loop]
//   while True:
//     _nb.check()
//     led.value(1)
//     await uasyncio.sleep_ms(100)
//
// [controls_repeat_ext: 5回]
//   for count in range(5):
//     _nb.check()
//     led.toggle()
//
// [controls_whileUntil: x > 10 になるまで]
//   while not x > 10:
//     _nb.check()
//     x = x + 1
//
// [controls_for: i を 1 から 10 まで]
//   __start = 1
//   __end = 10
//   __step = 1
//   for i in range(__start, __end + 1 if __step >= 0 else __end - 1, __step):
//     _nb.check()
//     print(i)
// ──────────────────────────────────────────────────────────────
