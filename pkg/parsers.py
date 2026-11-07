"""Parser file KSEI / IDX -> struktur {k, d, data} yang SAMA dengan parse() di dashboard asli.

Port 1:1 dari JavaScript (fungsi n, iso, parse, SAN) agar data yang dibaca kalkulasi dashboard
identik. Satu perbaikan disengaja: file yang berisi BANYAK tanggal (tipe / >=1% / klasifikasi)
dipisah per tanggal. Versi lama memakai tanggal baris TERAKHIR untuk semua baris.
"""
import csv
import io
import re
from datetime import datetime, timedelta

PARSER_VERSION = "2.0-py"

MO = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "MAY": 5, "JUN": 6, "JUL": 7,
      "AGU": 8, "AUG": 8, "SEP": 9, "OKT": 10, "OCT": 10, "NOV": 11, "DES": 12, "DEC": 12}

_FLOAT = re.compile(r"\s*[+-]?(?:\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?)")


def clean(x):
    """Angka bulat -> int (sama dengan JSON.stringify di JS)."""
    if isinstance(x, float) and x == x and abs(x) < 1e15 and x == int(x):
        return int(x)
    return x


def num(v):
    """n(v) di dashboard: angka apa adanya, selain itu parseFloat(teks tanpa koma) || 0."""
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return clean(v) if v == v else 0
    s = "" if v is None else str(v).replace(",", "")
    m = _FLOAT.match(s)
    if not m:
        return 0
    r = float(m.group())
    return clean(r) if r == r else 0


def pct(v):
    """PC(v) di dashboard untuk kolom persentase."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return clean(v)
    s = "" if v is None else str(v)
    s = s.replace("%", "")
    s = re.sub(r"\s", "", s)
    s = re.sub(r",(?=\d{1,2}$)", ".", s)
    s = s.replace(",", "")
    m = _FLOAT.match(s)
    r = float(m.group()) if m else 0.0
    return clean(r) if r == r and r else 0


_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y")


def iso(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, str):
        s = v.strip()
        m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m:
            return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
        for f in _DATE_FORMATS:
            try:
                return datetime.strptime(s, f).strftime("%Y-%m-%d")
            except ValueError:
                pass
    try:
        serial = float(v)
        return (datetime(1899, 12, 30) + timedelta(days=round(serial))).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return ""


def sanitize_sat(o):
    """SAN(): persentase >100.01 -> 0 (dihitung sbg rusak); bila semua <=1 dianggap pecahan -> x100."""
    mx, bd = 0, 0
    for rows in o.values():
        for r in rows:
            if r[4] > 100.01:
                r[4] = 0
                bd += 1
            if r[4] > mx:
                mx = r[4]
    if not bd and 0 < mx <= 1:
        for rows in o.values():
            for r in rows:
                r[4] = clean(r[4] * 100)
    return bd


# ---------------------------------------------------------------- baca file -> baris

def rows_from_csv_text(text):
    """Setara XLSX.read(type:'string', raw:true) + sheet_to_json(header:1, defval:null)."""
    if text.startswith("\ufeff"):
        text = text[1:]
    rows = [[(c if c != "" else None) for c in r] for r in csv.reader(io.StringIO(text, newline=""))]
    w = max((len(r) for r in rows), default=0)
    return [r + [None] * (w - len(r)) for r in rows]


def _g(r, i):
    return r[i] if 0 <= i < len(r) else None


def _date_from_label(s, rx=r"(\d+)-(\w+)-(\d+)"):
    m = re.search(rx, str(s))
    if not m or m.group(2).upper() not in MO:
        return None
    return "%s-%02d-%02d" % (m.group(3), MO[m.group(2).upper()], int(m.group(1)))


class ParseError(Exception):
    pass


def parse(a, fname=""):
    """-> list[{'k','d','data'}] atau None bila format tidak dikenali."""
    hi = next((i for i, r in enumerate(a) if r and (
        "Kode Efek" in r or "Penutupan" in r or "SHARE_CODE" in r or "SHARE CODE" in r
        or _g(r, 2) == "NUMBER_OF_SHARES")), -1)
    if hi < 0:
        return None
    h = a[hi]
    o, nm = {}, {}

    if "Penutupan" in h:                                   # Ringkasan Saham IDX (harga)
        m = re.search(r"(\d{4})(\d{2})(\d{2})", fname or "")
        if m:
            d = "%s-%s-%s" % m.groups()
        else:
            t = re.search(r"(\d+) (\w+) (\d+)", str(_g(a[hi + 1], 6)))
            if not t or t.group(2).upper() not in MO:
                return None
            d = "%s-%02d-%02d" % (t.group(3), MO[t.group(2).upper()], int(t.group(1)))
        idx = [10, 4, 12, 13, 14, 24, 23, 5, 8, 9, 15, 16, 17, 18, 19, 21, 25]
        for r in a[hi + 1:]:
            if r and _g(r, 1):
                o[r[1]] = [num(_g(r, i)) for i in idx] if num(_g(r, 12)) else [num(_g(r, 10)), num(_g(r, 4))]
                nm[r[1]] = r[2]
        return [{"k": "px", "d": d, "data": o}, {"k": "nm", "d": "-", "data": nm}]

    if "Kode Efek" in h:                                   # kepemilikan >5% harian
        d = _date_from_label(_g(h, 14))
        if not d:
            return None
        ag, cur = {}, None
        for r in a[hi + 2:]:
            if not r or not _g(r, 1):
                continue
            c = r[1]
            if r[0] is not None or cur is None or cur[0] != c:
                cur = [c, _g(r, 4) or _g(r, 3), _g(r, 10)]
            if _g(r, 2):
                nm[c] = r[2]
            k = "%s|%s" % (c, cur[1])
            if k not in ag:
                ag[k] = [c, [cur[1], cur[2], 0, 0]]
            ag[k][1][2] = clean(ag[k][1][2] + num(_g(r, 11)))
            ag[k][1][3] = clean(ag[k][1][3] + num(_g(r, 14)))
        for c, e in ag.values():
            o.setdefault(c, []).append(e)
        return [{"k": "days", "d": d, "data": o}, {"k": "nm", "d": "-", "data": nm}]

    if _g(h, 2) == "NUMBER_OF_SHARES":                     # tipe investor
        per = {}
        for r in a[hi + 3:]:
            if r and _g(r, 0) and _g(r, 1):
                per.setdefault(iso(r[0]), {})[r[1]] = [num(x) for x in r[2:40]]
        return [{"k": "tipe", "d": d, "data": o} for d, o in per.items()]

    is_kl = ("SHARE_CODE" in h and any(re.match(r"(local|foreign)_", str(x or ""), re.I) for x in h)
             and not any(re.search(r"INVESTOR.?NAME", str(x or ""), re.I) for x in h))
    if "SHARE_CODE" in h and not is_kl:                    # kepemilikan >=1%
        def ix(rx, ne=None):
            for i, x in enumerate(h):
                s = str(x or "")
                if re.search(rx, s, re.I) and not (ne and re.search(ne, s, re.I)):
                    return i
            return -1
        fb = lambda i, k: k if i < 0 else i
        iN, iD = ix(r"NATIONALITY"), ix(r"DOMICILE")
        iS, iC = ix(r"SCRIPLESS"), ix(r"SCRIP", r"SCRIPLESS")
        iNm = fb(ix(r"INVESTOR.?NAME"), 3)
        iTy = fb(ix(r"INVESTOR.?(TYPE|CLASS)"), 4)
        iLF = fb(ix(r"LOCAL"), 5)
        iTt = fb(ix(r"TOTAL"), 10)
        iPc = fb(ix(r"PERCENT|PCT|%"), 11)
        per = {}
        for r in a[hi + 1:]:
            if r and _g(r, 0) and _g(r, 1):
                d = iso(r[0])
                lf = _g(r, iLF)
                per.setdefault(d, {}).setdefault(r[1], []).append([
                    _g(r, iNm), _g(r, iTy), "" if lf is None else str(lf).strip(),
                    num(_g(r, iTt)), pct(_g(r, iPc)),
                    None if iN < 0 else _g(r, iN), None if iD < 0 else _g(r, iD),
                    None if iS < 0 else num(_g(r, iS)), None if iC < 0 else num(_g(r, iC))])
                nm[r[1]] = _g(r, 2)
        out = [{"k": "sat", "d": d, "data": o} for d, o in per.items()]
        return out + [{"k": "nm", "d": "-", "data": nm}]

    per = {}                                               # klasifikasi (header 'SHARE CODE')
    for r in a[hi + 1:]:
        if r and _g(r, 0) and _g(r, 1):
            per.setdefault(iso(r[0]), {})[r[1]] = [num(x) for x in r[3:43]]
            nm[r[1]] = nm.get(r[1]) or _g(r, 2)
    out = [{"k": "kl", "d": d, "data": o} for d, o in per.items()]
    return out + [{"k": "klc", "d": "-", "data": ["null" if x is None else str(x) for x in h[3:43]]}, {"k": "nm", "d": "-", "data": nm}]
