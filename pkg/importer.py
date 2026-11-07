"""Pembaca sumber data lama + jalur impor bersama (dipakai server.py, migrate.py, validate.py)."""
import json, re
from pathlib import Path
import parsers, store

ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")


def read_text(path):
    raw = Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    raise ValueError("encoding tidak dikenali: %s" % path)


def parse_text(text, fname):
    """Teks CSV -> (items siap simpan, daftar dilewati). Aturan SAN ala dashboard: sat rusak dilewati."""
    items = parsers.parse(parsers.rows_from_csv_text(text), fname)
    if not items:
        return None, ["format tidak dikenali"]
    keep, skipped = [], []
    for x in items:
        if x["k"] == "sat":
            bad = parsers.sanitize_sat(x["data"])
            if bad:
                skipped.append("%s: %d baris persentase tidak valid" % (x["d"], bad)); continue
        if x["k"] in store.PER_DATE and not x["data"]:
            continue
        keep.append(x)
    return keep, skipped


# ---- sumber lama -> list item {k,d,data}

def embedded_from_json(path):
    D = json.loads(Path(path).read_text(encoding="utf-8"))
    return embedded_items(D)


def embedded_from_html(path):
    """Ambil objek D yang tertanam di index.html lama (const ...,D={...};)."""
    s = Path(path).read_text(encoding="utf-8", errors="replace")
    i = s.index("D={\"px\"") + 2
    D, _ = json.JSONDecoder().raw_decode(s[i:])
    return embedded_items(D)


def embedded_items(D):
    out = []
    for k in store.PER_DATE:
        for d in sorted(D.get(k, {})):
            out.append({"k": k, "d": d, "data": D[k][d]})
    if D.get("nm"): out.append({"k": "nm", "d": "-", "data": D["nm"]})
    if D.get("klc"): out.append({"k": "klc", "d": "-", "data": D["klc"]})
    if D.get("hc"): out.append({"k": "hc", "d": "-", "data": D["hc"]})
    return out


def csv_files(csv_dir):
    return sorted(Path(csv_dir).glob("*.csv"), key=lambda p: (p.stat().st_mtime, p.name))


def usr_from_json(path):
    if not Path(path).exists():
        raise SystemExit("Berkas ekspor tidak ditemukan: %s (opsi --usr-json hanya dipakai bila Anda punya berkas ekspor IndexedDB/cloud; kalau tidak, jangan dipakai)" % path)
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["items"] if isinstance(data, dict) else data
