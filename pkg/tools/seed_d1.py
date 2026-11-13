"""Seed a fresh D1 screener DB with the rows required by the cloud signal worker."""
import argparse
import datetime
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import database


BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "screener.db"
PX_DAYS = 21


def _rows(conn, table, where="", params=()):
    columns = [row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)]
    if not columns:
        return columns, []
    sql = "SELECT %s FROM %s" % (", ".join('"%s"' % name for name in columns), table)
    if where:
        sql += " WHERE " + where
    result = conn.execute(sql, params).fetchall()
    return columns, [tuple(row) for row in result]


def _insert(conn, table, columns, rows):
    if not rows:
        return 0
    col_sql = ", ".join('"%s"' % name for name in columns)
    placeholders = ",".join("?" for _ in columns)
    sql = "INSERT INTO %s (%s) VALUES (%s)" % (table, col_sql, placeholders)
    conn.executemany(sql, rows)
    return len(rows)


def seed(source_path=SOURCE, apply=False):
    if apply and not os.environ.get("SCREENER_D1_API_URL"):
        raise SystemExit("Atur SCREENER_D1_API_URL dan SCREENER_D1_API_TOKEN untuk target D1.")
    source = sqlite3.connect("file:%s?mode=ro" % Path(source_path).resolve().as_posix(), uri=True)
    source.row_factory = sqlite3.Row
    target = database.connect() if apply else None
    try:
        if target:
            existing = target.execute("SELECT COUNT(*) FROM shared_datasets").fetchone()[0]
            if existing:
                raise SystemExit("Target D1 tidak kosong (%s dataset). Seeder hanya untuk D1 baru." % existing)

        px_dates = [row[0] for row in source.execute(
            "SELECT data_date FROM shared_datasets WHERE dataset_type='px' ORDER BY data_date DESC LIMIT ?",
            (PX_DAYS,),
        )]
        if len(px_dates) < PX_DAYS:
            raise SystemExit("Database lokal hanya memiliki %s tanggal harga; perlu %s." % (len(px_dates), PX_DAYS))
        px_ids = [row[0] for row in source.execute(
            "SELECT id FROM shared_datasets WHERE dataset_type='px' AND data_date IN (%s)" % ",".join("?" for _ in px_dates),
            tuple(px_dates),
        )]
        other_ids = [row[0] for row in source.execute(
            "SELECT s.id FROM shared_datasets s JOIN ("
            "SELECT dataset_type,MAX(data_date) AS latest FROM shared_datasets "
            "WHERE dataset_type IN ('days','tipe','sat','kl','nm','klc') GROUP BY dataset_type"
            ") latest ON s.dataset_type=latest.dataset_type AND s.data_date=latest.latest"
        )]
        selected_ids = px_ids + other_ids
        ds_cols, datasets = _rows(source, "shared_datasets", "id IN (%s)" % ",".join("?" for _ in selected_ids), tuple(selected_ids))
        id_marks = ",".join("?" for _ in selected_ids)
        rec_cols, records = _rows(source, "shared_records", "dataset_id IN (%s)" % id_marks, tuple(selected_ids))
        user_cols, users = _rows(source, "app_users")
        pref_cols, prefs = _rows(source, "user_preferences")
        watch_cols, watchlists = _rows(source, "user_watchlists")
        fund_cols, funds = _rows(source, "fundamentals_cache")
        today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).date().isoformat()
        alert_cols, alerts = _rows(source, "alert_log", "day=?", (today,))
        outbox_cols, outbox = _rows(source, "telegram_outbox", "day=? AND status IN ('pending','processing')", (today,))
        meta_cols, metadata = _rows(source, "app_meta", "key IN ('schema_version','data_version')")

        plan = [
            ("app_users", user_cols, users),
            ("shared_datasets", ds_cols, datasets),
            ("shared_records", rec_cols, records),
            ("user_preferences", pref_cols, prefs),
            ("user_watchlists", watch_cols, watchlists),
            ("fundamentals_cache", fund_cols, funds),
            ("alert_log", alert_cols, alerts),
            ("telegram_outbox", outbox_cols, outbox),
            ("app_meta", meta_cols, metadata),
        ]
        total = sum(len(rows) for _, _, rows in plan)
        if total > 30_000:
            raise SystemExit("Seed memilih %s row, melewati batas aman 30.000. Kurangi PX_DAYS atau tinjau dulu." % total)
        print("Rencana seed D1 baru:")
        print("  tanggal px:", ", ".join(sorted(px_dates)))
        for table, _, rows in plan:
            print("  %-20s %s row" % (table, len(rows)))
        print("  total                 %s row sumber; D1 juga menghitung penulisan index." % total)
        if not apply:
            print("Belum ada data yang diubah. Jalankan ulang dengan --apply setelah memeriksa rencana.")
            return
        for table, columns, rows in plan:
            written = _insert(target, table, columns, rows)
            print("seed %-20s %s" % (table, written), flush=True)
        print("Seed selesai. Periksa kuota D1 Row Metrics sebelum menjalankan workflow harian.")
    finally:
        if target:
            target.close()
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE), help="SQLite lokal sumber (default: pkg/screener.db)")
    parser.add_argument("--apply", action="store_true", help="Jalankan seed setelah target kosong diverifikasi")
    args = parser.parse_args()
    seed(args.source, args.apply)


if __name__ == "__main__":
    main()
