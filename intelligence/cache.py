import json
import shutil
from datetime import datetime

from config.settings import CACHE_DIR


def _path(doc_id, name):
    return CACHE_DIR / doc_id / f"{name}.json"


def cache_get(doc_id, name):
    p = _path(doc_id, name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def cache_set(doc_id, name, data):
    data["generated_at"] = datetime.now().isoformat(timespec="seconds")
    p = _path(doc_id, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def clear_cache(doc_id):
    shutil.rmtree(CACHE_DIR / doc_id, ignore_errors=True)
