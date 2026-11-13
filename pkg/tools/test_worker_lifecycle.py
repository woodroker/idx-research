"""Uji lifecycle worker Telegram: tidak start saat import, start eksplisit, dan stop bersih."""
import ast
import os
import sys
import tempfile
import threading
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database
import telegram

tmp = Path(tempfile.mkdtemp(prefix="screener-worker-test-"))
database.DB_PATH = tmp / "test.db"
database.initialize()


def check(condition, message):
    print(("OK   " if condition else "GAGAL ") + message)
    assert condition, message


def telegram_threads():
    return [t for t in threading.enumerate() if t.name in ("telegram-sender", "telegram-scanner")]


check(not telegram_threads(), "import tidak menjalankan thread Telegram")
state = telegram.start(sender=True, scanner=False)
first_sender = telegram._sender_thread
check(state == {"sender": True, "scanner": False}, "sender saja dapat dijalankan")
state2 = telegram.start(sender=True, scanner=False)
check(telegram._sender_thread is first_sender and state2["sender"], "start berulang tidak menggandakan sender")
telegram.stop(timeout=2)
check(not telegram_threads(), "stop menghentikan sender dan membersihkan referensi thread")

state = telegram.start(sender=False, scanner=True)
check(state == {"sender": False, "scanner": True}, "scanner saja dapat dijalankan")
telegram.stop(timeout=2)
check(not telegram_threads(), "stop menghentikan scanner")


# Lease memastikan hanya satu proses worker aktif untuk database yang sama.
check(telegram.acquire_worker_lease("worker-A", lease_seconds=30), "worker pertama dapat mengambil lease")
check(not telegram.acquire_worker_lease("worker-B", lease_seconds=30), "worker kedua ditolak selama lease aktif")
check(telegram.renew_worker_lease("worker-A", lease_seconds=30), "pemilik dapat memperbarui lease")
check(telegram.worker_lease_status()["running"], "status lease terbaca lintas proses")
telegram.release_worker_lease("worker-A")
check(not telegram.worker_lease_status()["running"], "lease dilepas saat shutdown")
check(telegram.acquire_worker_lease("worker-B", lease_seconds=30), "worker berikutnya bisa mengambil lease setelah dilepas")
telegram.release_worker_lease("worker-B")
with database.connect() as conn:
    expired = {"owner": "worker-old", "heartbeat_at": time.time() - 60, "expires_at": time.time() - 30}
    conn.execute("INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (telegram._WORKER_LEASE_KEY, json.dumps(expired)))
check(telegram.acquire_worker_lease("worker-new", lease_seconds=30), "lease kedaluwarsa dapat diambil alih")
telegram.release_worker_lease("worker-new")

# Worker Telegram hanya boleh dimulai pada entry point server, bukan saat modul diimpor.
server_tree = ast.parse((ROOT / "server.py").read_text(encoding="utf-8"))
telegram_start_calls = [node for node in ast.walk(server_tree)
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "start" and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "telegram"]
main_guard = next((node for node in server_tree.body if isinstance(node, ast.If)
                   and isinstance(node.test, ast.Compare)
                   and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
                   and any(isinstance(part, ast.Constant) and part.value == "__main__"
                           for part in node.test.comparators)), None)
check(bool(telegram_start_calls) and main_guard is not None
      and all(main_guard.lineno < call.lineno <= main_guard.end_lineno for call in telegram_start_calls),
      "Telegram worker hanya dimulai saat server dijalankan, bukan saat import")

# Bila Flask terpasang, import server juga tidak boleh memulai worker.
try:
    import flask  # noqa: F401
    import pandas  # noqa: F401
    import werkzeug  # noqa: F401
except ModuleNotFoundError as exc:
    print("SKIP runtime import server: dependency belum dipasang (%s)" % exc.name)
else:
    import server  # noqa: F401
    check(not telegram_threads(), "import server tidak menjalankan thread Telegram")
print("SEMUA UJI LIFECYCLE WORKER LULUS")
