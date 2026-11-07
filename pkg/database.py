"""Database Model C (screener.db) - skema v2.
Perubahan dari v1: satu dataset per (jenis, tanggal) agar tidak tumpang tindih, kolom origin/parser_version,
tabel app_meta. Tabel lama (user, watchlist, audit_log) tidak diubah.
"""
from pathlib import Path
import sqlite3, shutil, datetime

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "screener.db"
BACKUP_DIR = BASE_DIR / "backups"
SCHEMA_VERSION = "2"

SCHEMA = r"""
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS app_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin','user')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- Jenis dataset (dataset_type): px, days, tipe, sat, kl  (per tanggal)
--                               nm, klc, hc              (global, data_date = '-')
CREATE TABLE IF NOT EXISTS shared_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_type TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    data_date TEXT NOT NULL DEFAULT '-',
    content_sha256 TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    imported_by INTEGER REFERENCES app_users(id),
    origin TEXT NOT NULL DEFAULT 'upload',
    parser_version TEXT NOT NULL DEFAULT '',
    UNIQUE(dataset_type, data_date)
);
CREATE INDEX IF NOT EXISTS idx_shared_datasets_type_date ON shared_datasets(dataset_type, data_date);
CREATE TABLE IF NOT EXISTS shared_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dataset_id INTEGER NOT NULL REFERENCES shared_datasets(id) ON DELETE CASCADE,
    security_code TEXT NOT NULL DEFAULT '',
    record_date TEXT,
    payload_json TEXT NOT NULL,
    UNIQUE(dataset_id, security_code)
);
CREATE INDEX IF NOT EXISTS idx_shared_records_code_date ON shared_records(security_code, record_date);
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id INTEGER PRIMARY KEY REFERENCES app_users(id) ON DELETE CASCADE,
    preferences_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS user_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
    security_code TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, security_code)
);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON user_watchlists(user_id);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER REFERENCES app_users(id),
    action TEXT NOT NULL,
    target TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS fundamentals_cache (
    security_code TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alert_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    kind TEXT NOT NULL,
    day TEXT NOT NULL,
    price REAL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alert_day ON alert_log(day, kind, status);
CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def _cols(conn, table):
    return [r["name"] for r in conn.execute("PRAGMA table_info(%s)" % table)]


def _upgrade_v1(conn):
    """screener.db v1 (kosong atau berisi) -> v2 tanpa menghapus data."""
    cols = _cols(conn, "shared_datasets")
    if "origin" in cols:
        return
    n = conn.execute("SELECT COUNT(*) FROM shared_datasets").fetchone()[0]
    if n == 0:   # kosong: bangun ulang bersih agar constraint UNIQUE lama (dengan sha) hilang
        conn.executescript("DROP TABLE shared_records; DROP TABLE shared_datasets;")
        conn.executescript(SCHEMA)
        return
    dup = conn.execute("SELECT dataset_type,data_date,COUNT(*) c FROM shared_datasets GROUP BY 1,2 HAVING c>1").fetchall()
    if dup:
        raise RuntimeError("v1 berisi dataset ganda (jenis+tanggal sama): %s. Bereskan dulu." % [tuple(d) for d in dup[:5]])
    conn.execute("ALTER TABLE shared_datasets ADD COLUMN origin TEXT NOT NULL DEFAULT 'upload'")
    conn.execute("ALTER TABLE shared_datasets ADD COLUMN parser_version TEXT NOT NULL DEFAULT ''")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_shared_datasets_type_date ON shared_datasets(dataset_type, data_date)")


def initialize():
    with connect() as conn:
        conn.executescript(SCHEMA)
        _upgrade_v1(conn)
        conn.execute("INSERT INTO app_meta(key,value) VALUES('schema_version',?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (SCHEMA_VERSION,))
        conn.execute("INSERT OR IGNORE INTO app_meta(key,value) VALUES('data_version','0')")


def backup(tag="manual"):
    """Salinan konsisten screener.db ke backups/ (aman walau DB sedang dipakai)."""
    BACKUP_DIR.mkdir(exist_ok=True)
    if not DB_PATH.exists():
        return None
    dest = BACKUP_DIR / ("screener-%s-%s.db" % (datetime.datetime.now().strftime("%Y%m%d-%H%M%S"), tag))
    src = connect()
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close(); dst.close()
    return dest


if __name__ == "__main__":
    initialize()
    print("Database Model C siap (skema v%s): %s" % (SCHEMA_VERSION, DB_PATH))
