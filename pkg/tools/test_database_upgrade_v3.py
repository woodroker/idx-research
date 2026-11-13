"""Uji upgrade database v2 -> v3 tanpa ketergantungan pada sibling project."""
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import database as current

tmp = Path(tempfile.mkdtemp(prefix="screener-db-upgrade-"))
db_path = tmp / "screener.db"
# Fixture minimal v2: app_meta sudah ada, telegram_outbox belum dibuat.
conn = sqlite3.connect(db_path)
conn.execute("CREATE TABLE app_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
conn.execute("INSERT INTO app_meta(key,value) VALUES('schema_version','2')")
conn.execute("INSERT INTO app_meta(key,value) VALUES('data_version','123')")
conn.execute("INSERT INTO app_meta(key,value) VALUES('custom_test','preserve-me')")
conn.commit()
conn.close()

current.DB_PATH = db_path
current.BACKUP_DIR = tmp / "backups"
current.initialize()
with current.connect() as conn:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "telegram_outbox" in tables
    assert conn.execute("SELECT value FROM app_meta WHERE key='schema_version'").fetchone()[0] == "3"
    assert conn.execute("SELECT value FROM app_meta WHERE key='data_version'").fetchone()[0] == "123"
    assert conn.execute("SELECT value FROM app_meta WHERE key='custom_test'").fetchone()[0] == "preserve-me"
print("OK: upgrade v2 -> v3 menambahkan telegram_outbox tanpa menghapus metadata lama")
