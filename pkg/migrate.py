"""Migrasi data lama -> screener.db. Aman diulang (idempoten). Selalu membuat backup dulu.

Urutan sumber (sama dengan perilaku dashboard lama: data tertanam < file unggahan terbaru):
  1. data tertanam di index.html lama   (legacy/legacy_embedded_D.json atau --legacy-html)
  2. arsip CSV  data/*.csv               (urut waktu ubah; yang lebih baru menimpa tanggal yang sama)
  3. isi IndexedDB (--usr-json)          (hanya MENGISI yang belum ada; beda isi dicatat sebagai konflik)
Contoh:  python migrate.py
         python migrate.py --csv-dir data --usr-json export_indexeddb.json
"""
import argparse, json, sys, time
from pathlib import Path
import database, importer, store

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-json", default=str(BASE / "legacy" / "legacy_embedded_D.json"))
    ap.add_argument("--legacy-html", help="index.html lama (alternatif untuk --legacy-json)")
    ap.add_argument("--csv-dir", default=str(BASE / "data"))
    ap.add_argument("--usr-json", help="berkas hasil ekspor IndexedDB (tombol di dashboard)")
    ap.add_argument("--no-backup", action="store_true")
    a = ap.parse_args()

    database.initialize()
    if not a.no_backup:
        b = database.backup("sebelum-migrasi")
        print("Backup:", b or "(DB baru, tidak ada yang dibackup)")
    report = {"embedded": None, "csv": None, "usr": None}

    # 1. data tertanam
    src = None
    if a.legacy_html and Path(a.legacy_html).exists():
        items, src = importer.embedded_from_html(a.legacy_html), a.legacy_html
    elif Path(a.legacy_json).exists():
        items, src = importer.embedded_from_json(a.legacy_json), a.legacy_json
    else:
        items = []
        print("! data tertanam tidak ditemukan, dilewati")
    if items:
        res = store.save_items(items, "index.html-tertanam", origin="embedded", mode="fill")
        c = {}
        for r in res: c[r["status"]] = c.get(r["status"], 0) + 1
        report["embedded"] = c
        print("1. Data tertanam  (%s): %d dataset ->" % (Path(src).name, len(items)), c)

    # 2. arsip CSV
    files = importer.csv_files(a.csv_dir) if Path(a.csv_dir).exists() else []
    if files:
        t0, c, bad, skipped_all, replaced = time.time(), {}, [], [], []
        for i, p in enumerate(files, 1):
            try:
                keep, skipped = importer.parse_text(importer.read_text(p), p.name)
                if keep is None or not any(x["k"] in store.PER_DATE for x in keep):
                    bad.append((p.name, "; ".join(skipped) or "tidak ada data")); continue
                skipped_all += [(p.name, s) for s in skipped]
                for r in store.save_items(keep, p.name, origin="csv", mode="replace"):
                    c[r["status"]] = c.get(r["status"], 0) + 1
                    if r["status"] == "diganti": replaced.append((r["kind"], r["date"], p.name))
                    if r.get("warning"): print("   ! %s: %s" % (p.name, r["warning"]))
            except Exception as exc:
                bad.append((p.name, str(exc)))
            if i % 25 == 0 or i == len(files):
                print("   ... %d/%d file (%.0f dtk)" % (i, len(files), time.time() - t0), end="\r")
        print()
        report["csv"] = c
        print("2. Arsip CSV: %d file ->" % len(files), c)
        if replaced:
            print("   Tanggal yang ditimpa (sumber ganda / lebih baru) - dicatat di audit_log:")
            for k, d, f in replaced[:20]: print("     %s %s <- %s" % (k, d, f))
        for f, why in bad: print("   GAGAL %s: %s" % (f, why))
        for f, why in skipped_all: print("   DILEWATI %s: %s" % (f, why))
    else:
        print("2. Arsip CSV: tidak ada file di", a.csv_dir)

    # 3. IndexedDB
    if a.usr_json:
        items = importer.usr_from_json(a.usr_json)
        res = store.save_items([x for x in items if x.get("k") in store.ALL_KINDS], "indexeddb-lama", origin="idb", mode="fill")
        c = {}
        for r in res: c[r["status"]] = c.get(r["status"], 0) + 1
        report["usr"] = c
        print("3. IndexedDB: %d item ->" % len(items), c)
        conf = [r for r in res if r.get("conflicts")]
        for r in conf[:20]: print("   KONFLIK (DB dipertahankan): %s %s" % (r["kind"], r["date"]))

    with database.connect() as conn:
        print("\nRingkasan screener.db:")
        for k, v in store.summary(conn).items():
            print("  %-5s %4d dataset  %s .. %s  %d record" % (k, v["datasets"], v["first"], v["last"], v["records"]))
    print("\nLanjut: python validate.py")


if __name__ == "__main__":
    sys.exit(main())
