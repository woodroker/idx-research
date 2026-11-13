"""Offline checks for the versioned, persistent /api/data gzip cache."""
import gzip
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database
import server
import store


old_db_path = database.DB_PATH
old_cache_path = server.DATA_CACHE_PATH
old_cache = server._cache
tmp = Path(tempfile.mkdtemp(prefix="screener-data-cache-test-"))
database.DB_PATH = tmp / "test.db"
server.DATA_CACHE_PATH = tmp / "api-data.gz"
server._cache = {"v": None, "raw": b"", "gz": b""}

try:
    database.initialize()
    store.save_items([
        {"k": "px", "d": "2026-11-12", "data": {"BBCA": [1000, 990, 10, 1.01, 200000, 200000000, 10, 995, 1010, 980, 0, 0, 0, 0, 0, 0, 0]}},
        {"k": "nm", "d": "-", "data": {"BBCA": "Bank Central Asia"}},
    ], "fixture.csv", origin="test")
    client = server.app.test_client()
    headers = {"Accept-Encoding": "gzip"}

    first = client.get("/api/data", headers=headers)
    assert first.status_code == 200 and first.headers.get("Content-Encoding") == "gzip"
    assert json.loads(gzip.decompress(first.data))["px"]["2026-11-12"]["BBCA"][0] == 1000
    assert server.DATA_CACHE_PATH.exists()

    # Simulate a process restart: the version-matched disk cache must avoid rebuilding JSON.
    server._cache = {"v": None, "raw": b"", "gz": b""}
    with patch.object(server.store, "build_data_json", side_effect=AssertionError("cache miss")):
        restarted = client.get("/api/data", headers=headers)
    assert restarted.status_code == 200
    assert json.loads(gzip.decompress(restarted.data))["nm"]["BBCA"] == "Bank Central Asia"

    # A newer data version must discard the stale disk cache and rebuild.
    store.save_items([
        {"k": "px", "d": "2026-11-13", "data": {"BBCA": [1010, 1000, 10, 1.01, 210000, 212100000, 10, 1000, 1020, 990, 0, 0, 0, 0, 0, 0, 0]}},
    ], "next.csv", origin="test")
    with patch.object(server.store, "build_data_json", wraps=store.build_data_json) as build:
        changed = client.get("/api/data", headers=headers)
    assert build.call_count == 1
    assert json.loads(gzip.decompress(changed.data))["px"]["2026-11-13"]["BBCA"][0] == 1010
    print("OK: cache gzip tersimpan, dipakai setelah restart, dan dibangun ulang saat versi data berubah")
finally:
    database.DB_PATH = old_db_path
    server.DATA_CACHE_PATH = old_cache_path
    server._cache = old_cache
