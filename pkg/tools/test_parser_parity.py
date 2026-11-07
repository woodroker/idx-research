"""Uji paritas: parser Python (parsers.py) vs fungsi parse() ASLI di index.html (dijalankan di Node).
Memakai data sintetis yang meniru format file KSEI/IDX. Jalankan: python tools/test_parser_parity.py
Butuh: node. legacy/parse_asli.js = salinan parse()/n()/iso()/SAN() dari index.html lama."""
import json, os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import parsers

JS_MODULE = os.environ.get("JS_MODULE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legacy", "parse_asli.js"))
random.seed(7)
CODES = ["AADI", "AALI", "ABBA", "BBCA", "GOTO", "TLKM"]

def pad(r, w): return r + [None] * (w - len(r))

def px_rows():
    hdr = ["No", "Kode Saham", "Nama Perusahaan", "Remarks", "Sebelumnya", "Open Price", "Tanggal Perdagangan Terakhir",
           "First Trade", "Tertinggi", "Terendah", "Penutupan", "Selisih", "Volume", "Nilai", "Frekuensi", "Index Individual",
           "Offer", "Offer Volume", "Bid", "Bid Volume", "Listed Shares", "Tradable Shares", "Weight For Index",
           "Foreign Sell", "Foreign Buy", "Non Regular Volume"]
    rows = [hdr]
    for i, c in enumerate(CODES):
        vol = 0 if c == "ABBA" else random.randint(1000, 9_000_000)
        r = [str(i + 1), c, c + " Tbk.", "--MO1", str(random.randint(50, 9000)), "0", "02 Feb 2026"] + \
            [str(random.randint(50, 9000)) for _ in range(3)] + [str(random.randint(50, 9000)), "-125", str(vol),
             "{:,}".format(random.randint(1, 10**11)), "1224", "591.5", "7300", "44300", "7250", "1,000", "1924688333",
             "5,400,000", "0.5", "3,222,500", "4350900", "0"]
        rows.append(r)
    return [pad(r, 26) for r in rows]

def days_rows():
    rows = [["KEPEMILIKAN EFEK DIATAS 5% per tanggal 29 May 2026"] + [None] * 17, [None] * 18,
            ["No", "Kode Efek", "Nama Emiten", "Nama Pemegang Rekening Efek", "Nama Pemegang Saham", "Nama Rekening Efek",
             "Alamat", "Alamat (Lanjutan)", "Kebangsaan", "Domisili", "Status (Lokal/Asing)", "Kepemilikan Per 26-MAY-2026", None, None,
             "Kepemilikan Per 29-MAY-2026", None, None, "Perubahan"],
            [None] * 11 + ["Jumlah Saham", "Saham Gabungan", "Persentase"] * 2 + [None]]
    n = 1
    for c in CODES[:4]:
        for j in range(3):
            first = j == 0 or random.random() < .3
            r = [str(n) if first else None, c, c + " Tbk, PT" if first else None, "BUT BANK " + str(j), "HOLDER " + str(j % 2) if j != 2 else None,
                 "REK", "x", "y", None, "ID", "L" if j % 2 else "A", "{:,}".format(random.randint(1, 10**9)), "3,200,142,830", "41.10",
                 "{:,}".format(random.randint(1, 10**9)), "3,200,142,830", "41.10", "0"]
            rows.append(r); n += first
    rows.append([None] * 18)
    return rows

def tipe_rows(dates=("2026-01-30 00:00:00",)):
    rows = [["KSEI is the central depository..."] + [None] * 39, ["DATE", "STOCK_CODE", "NUMBER_OF_SHARES", "DOMESTIC"] + [None] * 36,
            [None, None, None, "CP: Corporate"] + [None] * 36, [None, None, None, "<5%", ">=5%"] * 1 + [None] * 35]
    for d in dates:
        for c in CODES:
            rows.append([d, c, str(random.randint(10**8, 10**10))] + [str(random.choice([0, random.randint(0, 10**9), "", "-"])) if False else
                         random.choice(["0", str(random.randint(0, 10**9)), "{:,}".format(random.randint(0, 10**9))]) for _ in range(37)])
    return [pad(r, 40) for r in rows]

def sat_rows(pcts=("41,10", "5.25%", "12.3", "0.5")):
    hdr = ["DATE", "SHARE_CODE", "ISSUER_NAME", "INVESTOR_NAME", "INVESTOR_TYPE", "LOCAL_FOREIGN", "NATIONALITY", "DOMICILE",
           "HOLDINGS_SCRIPLESS", "HOLDINGS_SCRIP", "TOTAL_HOLDING_SHARES", "PERCENTAGE"]
    rows = [["*Penafian: ..."] + [None] * 11, [None] * 12, hdr]
    for c in CODES[:4]:
        for j, p in enumerate(pcts):
            rows.append(["2026-02-27 00:00:00", c, c + " Tbk", "INVESTOR %d" % j, random.choice(["CP", "ID", "MF"]), random.choice(["L", "F", " L "]),
                         "INDONESIA", "ID", "1,000", "0", "{:,}".format(random.randint(1, 10**9)), p])
    return rows

def kl_rows():
    hdr = ["DATE", "SHARE CODE", "ISSUER"] + ["CLS%d" % i for i in range(40)]
    rows = [["NUMBER OF SCRIPLESS SHARES BASED ON INVESTOR TYPE AND CLASSIFICATION"] + [None] * 42, [None] * 43, hdr]
    for c in CODES:
        rows.append(["2026-05-29", c, c + " Tbk"] + [random.choice(["0", str(random.randint(0, 10**8)), None]) for _ in range(40)])
    return rows

CASES = [("px", px_rows(), "Ringkasan_Saham-20260202.csv"), ("days", days_rows(), "peng-2026-05-29-00001-lima-persen.csv"),
         ("tipe", tipe_rows(), "peng-01-00006-tipe.csv"), ("sat", sat_rows(), "peng-02-00011-satu-persen.csv"),
         ("kl", kl_rows(), "peng-03-00001-klasifikasi.csv"),
         ("px-nofilenamedate", px_rows(), "Ringkasan Saham.csv")]

def js_parse(rows, fname):
    code = """const m=require(%s);const inp=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));
    const out=m.parse(inp.rows,inp.fname);for(const x of (out||[])) if(x.k==='sat') x.bad=m.SAN(x.data);
    process.stdout.write(JSON.stringify(out));""" % json.dumps(JS_MODULE)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"rows": rows, "fname": fname}, f)
    r = subprocess.run(["node", "-e", code, f.name], capture_output=True, text=True)
    os.unlink(f.name)
    if r.returncode: raise RuntimeError(r.stderr[:500])
    return json.loads(r.stdout or "null")

def py_parse(rows, fname):
    out = parsers.parse(rows, fname)
    for x in out or []:
        if x["k"] == "sat": x["bad"] = parsers.sanitize_sat(x["data"])
    return json.loads(json.dumps(out))   # normalisasi tipe seperti JSON

fails = 0
for name, rows, fn in CASES:
    rows = json.loads(json.dumps(rows))
    # sheet_to_json di JS memberi null utk sel kosong; sama dgn rows_from_csv_text
    a, b = js_parse(rows, fn), py_parse(rows, fn)
    ok = a == b
    print(("OK   " if ok else "BEDA ") + name, "-", [(x["k"], x["d"]) for x in (b or [])])
    if not ok:
        fails += 1
        for xa, xb in zip(a or [], b or []):
            if xa != xb: print("   JS:", json.dumps(xa)[:300], "\n   PY:", json.dumps(xb)[:300])
# lewat jalur CSV teks (tokenisasi) juga
import io, csv
for name, rows, fn in CASES[:5]:
    buf = io.StringIO(); csv.writer(buf).writerows([[("" if c is None else c) for c in r] for r in rows])
    r2 = parsers.rows_from_csv_text(buf.getvalue())
    a, b = js_parse(json.loads(json.dumps(rows)), fn), None
    out = parsers.parse(r2, fn)
    for x in out or []:
        if x["k"] == "sat": x["bad"] = parsers.sanitize_sat(x["data"])
    b = json.loads(json.dumps(out)); ok = a == b; fails += (not ok)
    print(("OK   " if ok else "BEDA ") + name + " (via teks CSV)")
# file multi-tanggal: perilaku baru (dipisah per tanggal) - JS lama menimpa semua ke tanggal terakhir
mt = py_parse(tipe_rows(("2026-01-30", "2026-02-27")), "x-tipe.csv")
print("multi-tanggal tipe ->", [(x["k"], x["d"], len(x["data"])) for x in mt])
sys.exit(1 if fails else 0)
