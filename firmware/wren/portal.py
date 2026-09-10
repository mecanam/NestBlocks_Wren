# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# portal.py — キャプティブポータル応答 (仕様書 §7.3)
# OS の接続確認に成功応答を返し、接続用画面の自動表示を抑える。

# パス → (ステータス, Content-Type, ボディ)
_RESPONSES = {
    '/connecttest.txt': (200, 'text/plain', b'Microsoft Connect Test'),
    '/hotspot-detect.html': (
        200, 'text/html',
        b'<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>'
    ),
    '/generate_204': (204, 'text/plain', b''),
    '/ncsi.txt': (200, 'text/plain', b'Microsoft NCSI'),
    '/success.txt': (200, 'text/plain', b'success'),
}

# キャプティブポータルパスの集合 (高速判定用)
PORTAL_PATHS = frozenset(_RESPONSES.keys())

def handle(path):
    """キャプティブポータルパスに対応するレスポンスタプルを返す。
    (status_code, content_type, body_bytes)
    未対応のパスは None を返す。
    """
    return _RESPONSES.get(path)
