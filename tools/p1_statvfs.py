# Phase 0 / P1 — LittleFS 空き容量確認
# Pico W の REPL か mpremote run で実行する
# 判定基準: 800 KB 以上

import os

def fmt(b):
    return f"{b:,} B  ({b / 1024:.1f} KB)"

stat = os.statvfs('/')
block_size  = stat[0]   # f_bsize
total_blocks = stat[2]  # f_blocks
free_blocks  = stat[3]  # f_bfree

total = block_size * total_blocks
free  = block_size * free_blocks
used  = total - free

print("=" * 40)
print("P1 — LittleFS 容量チェック")
print("=" * 40)
print(f"  合計  : {fmt(total)}")
print(f"  使用済: {fmt(used)}")
print(f"  空き  : {fmt(free)}")
print()
if free >= 800 * 1024:
    print("  [PASS] 800 KB 以上の空きあり")
else:
    print(f"  [FAIL] 不足 — あと {(800*1024 - free)/1024:.0f} KB 必要")
    print("         アセットをさらに削減してください")
print("=" * 40)
