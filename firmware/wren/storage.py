# NestBlocks Wren | Origin-ID: NBW-61bb60db-cdf4-40c7-9149-27aae51a9c8b
# Original Wren code: modification and redistribution require permission under the project LICENSE. Third-party components retain their own licenses.
# storage.py — プロジェクト CRUD (LittleFS /projects/ ディレクトリ)
# プロジェクトは JSON ファイルとして保存する。
# ファイル名: {id}.json  (id は 8 文字の 16 進数)
# 仕様書 §5.1

import os
import json

_DIR = '/projects'

def init():
    """起動時に /projects ディレクトリを作成する。"""
    try:
        os.mkdir(_DIR)
    except OSError:
        pass   # すでに存在する場合は無視

def _path(pid):
    return f'{_DIR}/{pid}.json'

def _gen_id():
    """8 文字の 16 進数 ID を生成する。"""
    import time
    import os as _os
    # time_ns が使えない MicroPython 環境では time.time() + urandom で代用
    try:
        seed = time.time_ns()
    except AttributeError:
        seed = int(time.time() * 1000)
    # os.urandom は使えるが entropy が少ない場合もある
    rnd = int.from_bytes(_os.urandom(4), 'big')
    return f'{(seed ^ rnd) & 0xFFFFFFFF:08x}'

# ── CRUD ──────────────────────────────────────────────────────

def list_projects():
    """全プロジェクトのメタデータリストを返す。
    各要素: {id, name, updated_at}
    """
    result = []
    try:
        entries = os.listdir(_DIR)
    except OSError:
        return result
    for fname in entries:
        if not fname.endswith('.json'):
            continue
        pid = fname[:-5]
        try:
            with open(_path(pid), 'r') as f:
                proj = json.load(f)
            result.append({
                'id':         pid,
                'name':       proj.get('name', ''),
                'updated_at': proj.get('updated_at', 0),
            })
        except Exception:
            pass
    # 更新日時降順
    result.sort(key=lambda x: x['updated_at'], reverse=True)
    return result

def get_project(pid):
    """プロジェクトの全データを返す。存在しなければ None。"""
    try:
        with open(_path(pid), 'r') as f:
            return json.load(f)
    except OSError:
        return None

def save_project(data):
    """プロジェクトを保存する。id がなければ新規作成。
    保存後のプロジェクトオブジェクトを返す。
    """
    import time
    pid = data.get('id') or _gen_id()
    data['id'] = pid
    data['updated_at'] = int(time.time())
    with open(_path(pid), 'w') as f:
        json.dump(data, f)
    return data

def delete_project(pid):
    """プロジェクトを削除する。削除できれば True、存在しなければ False。"""
    try:
        os.remove(_path(pid))
        return True
    except OSError:
        return False
