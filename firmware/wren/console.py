# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# console.py — コンソールリングバッファ (仕様書 §6.3)
# /api/console?since={seq} のポーリングに使用する。
# 各エントリには単調増加の seq 番号が付く。

_CAPACITY = 200          # 最大保持エントリ数
_buf      = []           # [(seq, text), ...]
_seq      = 0            # 次に割り当てるシーケンス番号

def reset():
    """プログラム実行前にバッファをクリアする。"""
    global _buf, _seq
    _buf = []
    _seq = 0

def push(text):
    """1行分のテキストをバッファに追加する。"""
    global _buf, _seq
    _buf.append((_seq, str(text)))
    _seq += 1
    if len(_buf) > _CAPACITY:
        _buf.pop(0)

def since(seq):
    """seq 以降のエントリを [(seq, text), ...] で返す。"""
    return [(s, t) for s, t in _buf if s >= seq]

def latest_seq():
    """現在の最大 seq 番号を返す (バッファが空なら -1)。"""
    return _buf[-1][0] if _buf else -1
