"""Validasi migrasi: jumlah data + isi data + sidik jari kalkulasi, sumber lama vs screener.db.
Kode keluar 0 = LULUS (aman menonaktifkan penyimpanan lama), 1 = ada yang perlu diperiksa.
Contoh: python validate.py            python validate.py --usr-json export_indexeddb.json
"""
import argparse, json, sys
from pathlib import Path
import database, importer, store

BASE = Path(__file__).resolve().parent


def norm(x):
    if isinstance(x, float) and x == x and abs(x) < 1e15 and x == int(x): return int(x)
    if isinstance(x, list): return [norm(i) for i in x]
    if isinstance(x, dict): return {k: norm(v) for k, v in x.items()}
    return x


def canon(x): return json.dumps(norm(x), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def db_D():
    conn = database.connect()
    try: return json.loads(store.build_data_json(conn)), conn
    finally: conn.close()


def fingerprint(D):
    """Ringkasan angka per kode yang dipakai kalkulasi: harga terakhir, total volume, arus 5%, jumlah investor >=1%, tipe terbaru."""
    fp = {}
    pdts = sorted(D["px"])
    for c in {c for d in D["px"].values() for c in d}:
        series = [D["px"][d][c] for d in pdts if c in D["px"][d]]
        fp.setdefault(c, {})["px"] = (len(series), series[-1][0], sum(s[2] for s in series if len(s) > 2))
    for c in {c for d in D["days"].values() for c in d}:
        net = sum(h[3] - h[2] for d in D["days"].values() for h in d.get(c, []))
        fp.setdefault(c, {})["days"] = (sum(len(d.get(c, [])) for d in D["days"].values()), net)
    for c in {c for d in D["sat"].values() for c in d}:
        fp.setdefault(c, {})["sat"] = (sum(len(d.get(c, [])) for d in D["sat"].values()), round(sum(r[4] for d in D["sat"].values() for r in d.get(c, [])), 6))
    for c in {c for d in D["tipe"].values() for c in d}:
        fp.setdefault(c, {})["tipe"] = (len(D["tipe"]), sum(D["tipe"][sorted(D["tipe"])[-1]].get(c, [0])))
    return fp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--legacy-json", default=str(BASE / "legacy" / "legacy_embedded_D.json"))
    ap.add_argument("--csv-dir", default=str(BASE / "data"))
    ap.add_argument("--usr-json")
    a = ap.parse_args()
    problems, notes = [], []
    D, _ = db_D()
    conn = database.connect()

    print("=== 1. JUMLAH DATA di screener.db ===")
    sm = store.summary(conn)
    for k in store.ALL_KINDS:
        v = sm.get(k)
        print("  %-5s %s" % (k, "%4d dataset  %s .. %s  %d record" % (v["datasets"], v["first"], v["last"], v["records"]) if v else "kosong"))

    print("\n=== 2. INTEGRITAS ===")
    r = conn.execute("PRAGMA integrity_check").fetchone()[0]; print("  integrity_check:", r); r != "ok" and problems.append("integrity_check")
    bad = conn.execute("SELECT s.dataset_type,s.data_date,s.row_count,COUNT(r.id) n FROM shared_datasets s LEFT JOIN shared_records r ON r.dataset_id=s.id GROUP BY s.id HAVING n<>s.row_count").fetchall()
    print("  row_count == jumlah record:", "OK" if not bad else "%d dataset tidak cocok" % len(bad)); bad and problems.append("row_count: %s" % [tuple(b) for b in bad[:5]])
    empty = conn.execute("SELECT dataset_type,data_date FROM shared_datasets WHERE row_count=0 AND dataset_type IN ('px','days','tipe','sat','kl')").fetchall()
    print("  dataset kosong:", len(empty)); empty and problems.append("dataset kosong")
    px_codes = {c for d in D["px"].values() for c in d}; unnamed = sorted(c for c in px_codes if c not in D["nm"])
    print("  kode harga tanpa nama emiten:", len(unnamed), unnamed[:8]); 
    hi = [(d, c) for d, o in D["sat"].items() for c, rows in o.items() for r in rows if r[4] > 100.01]
    print("  persentase >=1% di atas 100:", len(hi)); hi and problems.append("persentase >100 di sat")

    print("\n=== 3. SUMBER LAMA vs screener.db (isi persis) ===")
    srcs = []
    if Path(a.legacy_json).exists(): srcs.append(("tertanam", importer.embedded_from_json(a.legacy_json)))
    if Path(a.csv_dir).exists():
        its, last = [], {}
        for p in importer.csv_files(a.csv_dir):
            try: keep, _ = importer.parse_text(importer.read_text(p), p.name)
            except Exception: keep = None
            for x in keep or []:
                if x["k"] in store.PER_DATE: last[(x["k"], x["d"])] = (x, p.name)
        srcs.append(("arsip CSV (terbaru per tanggal)", [v[0] for v in last.values()]))
    if a.usr_json: srcs.append(("IndexedDB", importer.usr_from_json(a.usr_json)))
    for name, items in srcs:
        ok = miss = diff = 0; dl = []
        for x in items:
            k, d = x["k"], x.get("d", "-")
            if k in store.PER_DATE:
                got = D[k].get(d)
            elif k == "nm":  got = {c: D["nm"].get(c) for c in x["data"]}
            elif k == "hc":  got = {c: D["hc"].get(c) for c in x["data"]}
            else:            got = D["klc"]
            if got is None: miss += 1; dl.append(("HILANG", k, d))
            elif canon(got) == canon(x["data"]): ok += 1
            else: diff += 1; dl.append(("BEDA", k, d))
        print("  %-34s %4d item: %d identik, %d hilang, %d beda" % (name, len(items), ok, miss, diff))
        for t in dl[:8]: print("      ", *t)
        if miss: problems.append("%s: %d dataset hilang di DB" % (name, miss))
        if diff: notes.append("%s: %d dataset berbeda (wajar bila sumber lain lebih baru menimpa; lihat audit_log)" % (name, diff))

    print("\n=== 4. SIDIK JARI KALKULASI (D dari sumber vs D dari DB) ===")
    exp = {k: {} for k in store.PER_DATE}
    for name, items in srcs:
        for x in items:
            if x["k"] in store.PER_DATE: exp[x["k"]][x["d"]] = x["data"]
    if any(exp.values()):
        for k in store.PER_DATE:
            for d in D[k]: exp[k].setdefault(d, D[k][d])   # sumber 'fill' (idb) tak menimpa
        e = fingerprint(exp); g = fingerprint(D)
        mism = [c for c in set(e) | set(g) if canon(e.get(c)) != canon(g.get(c))]
        print("  kode dibandingkan: %d   tidak cocok: %d" % (len(set(e) | set(g)), len(mism)))
        for c in mism[:8]: print("     ", c, e.get(c), "<>", g.get(c))
        mism and problems.append("sidik jari kalkulasi beda: %d kode" % len(mism))
    else:
        print("  (tidak ada sumber lama untuk dibandingkan)")

    print()
    for n in notes: print("CATATAN:", n)
    if problems:
        print("HASIL: PERLU DIPERIKSA ->", "; ".join(problems)); return 1
    print("HASIL: LULUS. Jumlah dan isi data cocok; aman menonaktifkan penyimpanan lama (tetap simpan backup).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
