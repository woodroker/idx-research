"""Export a sanitized, repeatable market-data update bundle for Cloudflare D1."""
import argparse
import datetime
import gzip
import json
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
SOURCE = BASE / "pkg" / "screener.db"
PX_DAYS = 21
SUPPORT_TYPES = ("days", "tipe", "sat", "kl", "nm", "klc")


def _read_rows(conn, table, where="", params=(), columns=None):
    if columns is None:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)]
    if not columns:
        return [], []
    col_sql = ", ".join('"%s"' % name for name in columns)
    sql = "SELECT %s FROM \"%s\"" % (col_sql, table)
    if where:
        sql += " WHERE " + where
    return columns, [list(row) for row in conn.execute(sql, params).fetchall()]


def build_bundle(source_path=SOURCE, today=None):
    source_path = Path(source_path).resolve()
    source = sqlite3.connect("file:%s?mode=ro" % source_path.as_posix(), uri=True)
    source.row_factory = sqlite3.Row
    try:
        px_dates = [row[0] for row in source.execute(
            "SELECT DISTINCT data_date FROM shared_datasets "
            "WHERE dataset_type='px' ORDER BY data_date DESC LIMIT ?",
            (PX_DAYS,),
        )]
        if not px_dates:
            raise SystemExit("Tidak ada dataset harga (px) di database lokal.")
        px_marks = ",".join("?" for _ in px_dates)
        px_ids = [row[0] for row in source.execute(
            "SELECT id FROM shared_datasets WHERE dataset_type='px' "
            "AND data_date IN (%s)" % px_marks,
            tuple(px_dates),
        )]
        support_marks = ",".join("?" for _ in SUPPORT_TYPES)
        support_ids = [row[0] for row in source.execute(
            "SELECT s.id FROM shared_datasets AS s JOIN ("
            "SELECT dataset_type, MAX(data_date) AS latest FROM shared_datasets "
            "WHERE dataset_type IN (%s) GROUP BY dataset_type"
            ") AS latest ON s.dataset_type=latest.dataset_type AND s.data_date=latest.latest"
            % support_marks,
            SUPPORT_TYPES,
        )]
        selected_ids = sorted(set(px_ids + support_ids))
        if not selected_ids:
            raise SystemExit("Dataset harga/pendukung yang diperlukan tidak ditemukan.")
        marks = ",".join("?" for _ in selected_ids)
        datasets_cols, datasets = _read_rows(
            source, "shared_datasets", "id IN (%s)" % marks, tuple(selected_ids)
        )
        record_cols, records = _read_rows(
            source,
            "shared_records",
            "dataset_id IN (%s)" % marks,
            tuple(selected_ids),
            columns=("dataset_id", "security_code", "record_date", "payload_json"),
        )
        fund_cols, funds = _read_rows(source, "fundamentals_cache")
        if today is None:
            today = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=7))
            ).date().isoformat()
        meta_cols, metadata = _read_rows(
            source, "app_meta", "key IN ('schema_version','data_version')"
        )
        tables = {
            "shared_datasets": {"columns": datasets_cols, "rows": datasets},
            "shared_records": {"columns": record_cols, "rows": records},
            "fundamentals_cache": {"columns": fund_cols, "rows": funds},
            "app_meta": {"columns": meta_cols, "rows": metadata},
        }
        total = sum(len(table["rows"]) for table in tables.values())
        return {
            "format_version": 2,
            "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source_date_wib": today,
            "px_dates": sorted(px_dates),
            "dataset_ids": selected_ids,
            "source_rows": total,
            "tables": tables,
        }
    finally:
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=str(SOURCE), help="SQLite lokal sumber")
    parser.add_argument("--output", help="File .json.gz hasil (default: folder .d1_exports)")
    args = parser.parse_args()
    bundle = build_bundle(args.source)
    day = bundle["source_date_wib"].replace("-", "")
    output = Path(args.output) if args.output else BASE / ".d1_exports" / ("market-update-%s.json.gz" % day)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(output.suffix + ".tmp")
    with gzip.open(temp, "wt", encoding="utf-8", newline="") as stream:
        json.dump(bundle, stream, ensure_ascii=False, separators=(",", ":"))
    temp.replace(output)
    print("Bundle update siap:", output)
    print("Tanggal px:", ", ".join(bundle["px_dates"]))
    for name, table in bundle["tables"].items():
        print("  %-20s %s baris" % (name, len(table["rows"])))
    print("Total baris snapshot:", bundle["source_rows"])
    print("Akun, preferensi, watchlist, Telegram outbox, secrets, dan hasil backtest tidak disertakan.")


if __name__ == "__main__":
    main()
