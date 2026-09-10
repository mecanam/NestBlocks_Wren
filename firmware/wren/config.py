# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# config.py — Wren 設定
# チームごとに TEAM_NUM を変更する。

TEAM_NUM = 1               # 1 始まり。基板シールに印字された番号と一致させる。

SSID     = f'Wren-{TEAM_NUM:02d}'
PASSWORD = f'wren{TEAM_NUM:04d}'   # 例: チーム1 → wren0001
                                    # 本番前に強いパスワードに変更すること

# チャンネルをチーム番号で分散 (1 / 6 / 11 の繰り返し)
CHANNEL  = [1, 6, 11][(TEAM_NUM - 1) % 3]

IP       = '192.168.4.1'

VERSION  = '1.4.0'
EDITION  = 'wren'
