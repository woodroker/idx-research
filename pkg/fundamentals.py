"""Data fundamental per emiten dari yfinance (di-cache di SQLite) + analisis kualitas/valuasi.
Tidak menyentuh dataset px/KSEI. Semua ambang bisa diubah di bagian KONFIGURASI.
Catatan: cakupan data yfinance untuk saham IDX tidak merata (terutama saham kecil); nilai yang tidak tersedia = None (ditampilkan 'n/a').
"""
import datetime, json, os, threading, time, urllib.parse, urllib.request
from pathlib import Path
import database
from local_env import load_local_env


def _utcnow():
    """UTC naive (pengganti datetime.utcnow() yang deprecated)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

# ---- KONFIGURASI (ambang analisis) ----
# Skor gabungan (maks 14) & kuadran PBV x ROE/NPM/PE sesuai spesifikasi; semua ambang di sini
ROE_HI, ROE_LO = 15.0, 10.0
PBV_CHEAP, PBV_VCHEAP = 1.5, 1.0
PE_CHEAP, PE_VCHEAP = 15.0, 10.0
NPM_HI, NPM_MID = 15.0, 10.0
DER_OK, DER_MAX_HARD = 1.0, 1.5
EPS_UP, EPS_FLAT = 5.0, 0.0
BUY_MIN, HOLD_MIN = 11, 7           # skor 11-14 Mutiara Super | 7-10 Wajar/Layak Pantau | <7 Hindari
MIN_COMPONENTS = 4                  # komponen skor yang harus tersedia agar skor/sinyal ditampilkan
COE = 12.0            # cost of equity (%) -> ambang "ROE >= COE" dan dasar PBV wajar (fair PBV = ROE / COE)
FAIR_PBV_RANGE = (0.3, 3.0)
DER_MAX = 1.0         # "utang terkendali" jika DER < 1,0x (tidak berlaku utk sektor keuangan)
QUALITY_MIN = 60      # skor >= 60 dianggap berkualitas
MIN_TESTS = 4         # minimal uji yang dapat dihitung agar skor ditampilkan
CACHE_HOURS = 12
DY_SUSPECT = 25.0     # dividend yield (%) di atas ini ditandai tidak wajar
SALES_DROP_WARN = -10.0

_fetch_lock = threading.Lock()
_last_fetch = [0.0]


# ------------------------------------------------------------------ ambil data (yfinance)
def _series(df, names):
    """DataFrame yfinance (baris=item, kolom=tanggal) -> {tanggal_iso: nilai} untuk label pertama yang ada."""
    out = {}
    try:
        for n in names:
            if n in df.index:
                for col, v in df.loc[n].items():
                    if v == v and v is not None:
                        out[col.strftime("%Y-%m-%d")] = float(v)
                break
    except Exception:
        pass
    return out


def fetch_raw(code):
    import yfinance as yf
    t = yf.Ticker(code + ".JK")
    raw = {"code": code, "fetched": _utcnow().isoformat(timespec="seconds") + "Z", "info": {}, "q": [], "a": []}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    for k in ("longName", "sector", "industry", "marketCap", "trailingPE", "priceToBook", "returnOnEquity", "debtToEquity",
              "trailingEps", "profitMargins", "bookValue", "sharesOutstanding", "currentPrice", "mostRecentQuarter",
              "fiftyTwoWeekLow", "fiftyTwoWeekHigh"):
        if info.get(k) is not None:
            raw["info"][k] = info[k]
    try:
        q = t.quarterly_income_stmt
        rev = _series(q, ["Total Revenue", "Operating Revenue"]); ni = _series(q, ["Net Income", "Net Income Common Stockholders"])
        raw["q"] = [{"d": d, "rev": rev.get(d), "ni": ni.get(d)} for d in sorted(set(rev) | set(ni), reverse=True)]
    except Exception:
        pass
    try:
        a = t.income_stmt; b = t.balance_sheet
        rev = _series(a, ["Total Revenue", "Operating Revenue"]); ni = _series(a, ["Net Income", "Net Income Common Stockholders"])
        eq = _series(b, ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"])
        debt = _series(b, ["Total Debt"]); sh = _series(b, ["Ordinary Shares Number", "Share Issued"])
        raw["a"] = [{"d": d, "rev": rev.get(d), "ni": ni.get(d), "eq": eq.get(d), "debt": debt.get(d), "shares": sh.get(d)}
                    for d in sorted(set(rev) | set(ni) | set(eq), reverse=True)]
    except Exception:
        pass
    try:
        dv = t.dividends
        if dv is not None and len(dv):
            cutoff = dv.index.max() - datetime.timedelta(days=365)
            raw["div12"] = float(dv[dv.index > cutoff].sum())
    except Exception:
        pass
    try:
        h = t.history(period="1y")
        if h is not None and len(h):
            raw["low52"], raw["high52"] = float(h["Low"].min()), float(h["High"].max())
    except Exception:
        pass
    return raw


# ------------------------------------------------------------------ Alpha Vantage (pelengkap bila yfinance tidak punya field)
# Kunci dibaca dari env ALPHAVANTAGE_KEY atau alphavantage.json (TIDAK pernah dikirim ke browser). Paket gratis ~25 panggilan/hari.
AV_CFG = Path(__file__).resolve().parent / "alphavantage.json"
AV_DAILY = int(os.environ.get("SCREENER_AV_DAILY", "20"))
_av = {"day": None, "n": 0}
AV_MAP = {"PERatio": "trailingPE", "PriceToBookRatio": "priceToBook", "ReturnOnEquityTTM": "returnOnEquity", "ProfitMargin": "profitMargins",
          "MarketCapitalization": "marketCap", "EPS": "trailingEps", "BookValue": "bookValue", "SharesOutstanding": "sharesOutstanding",
          "Sector": "sector", "Industry": "industry", "Name": "longName"}
CORE = ("trailingPE", "priceToBook", "returnOnEquity", "profitMargins", "marketCap", "trailingEps", "sector")


def _av_key():
    load_local_env()
    if os.environ.get("ALPHAVANTAGE_KEY"):
        return os.environ["ALPHAVANTAGE_KEY"]
    try:
        return json.loads(AV_CFG.read_text(encoding="utf-8")).get("key") or ""
    except (OSError, ValueError):
        return ""


def fetch_av(code, http=None):
    """-> dict field yfinance-style dari OVERVIEW Alpha Vantage ({} bila tidak ada / limit)."""
    key = _av_key()
    if not key:
        return {}
    today = datetime.date.today().isoformat()
    if _av["day"] != today:
        _av["day"], _av["n"] = today, 0
    http = http or (lambda u: json.loads(urllib.request.urlopen(u, timeout=15).read().decode()))
    for suffix in (".JK", ".JKT"):
        if _av["n"] >= AV_DAILY:
            return {}
        _av["n"] += 1
        js = http("https://www.alphavantage.co/query?" + urllib.parse.urlencode({"function": "OVERVIEW", "symbol": code + suffix, "LU9037PKIO1BYZEW": key}))
        if js.get("Symbol"):
            out = {}
            for a, b in AV_MAP.items():
                v = js.get(a)
                if v in (None, "", "None", "-", "0"):
                    continue
                try:
                    out[b] = v if b in ("sector", "industry", "longName") else float(v)
                except ValueError:
                    pass
            return out
        if "Note" in js or "Information" in js:        # kena limit
            return {}
    return {}


def fill_missing(raw, http=None):
    """Lengkapi raw['info'] dari Alpha Vantage HANYA untuk field yang kosong. Nilai yfinance tidak pernah ditimpa."""
    info = raw.setdefault("info", {})
    if all(info.get(k) is not None for k in CORE):
        return raw
    try:
        extra = fetch_av(raw.get("code"), http)
    except Exception:
        extra = {}
    added = [k for k, v in extra.items() if info.get(k) is None and not info.update({k: v})]
    if added:
        raw["src"] = ["yfinance", "alphavantage"]
        raw["av_fields"] = added
    return raw


# ------------------------------------------------------------------ cache
def get_raw(code, force=False, fetcher=fetch_raw):
    """-> (raw, status) status: 'cache' | 'baru' | 'basi' (gagal ambil, pakai cache lama) ; raw None bila tidak ada sama sekali."""
    conn = database.connect()
    try:
        row = conn.execute("SELECT fetched_at,payload_json FROM fundamentals_cache WHERE security_code=?", (code,)).fetchone()
        if row:
            age = (_utcnow() - datetime.datetime.fromisoformat(row["fetched_at"].rstrip("Z"))).total_seconds() / 3600
            if age < CACHE_HOURS and not (force and age > 1 / 60):
                return json.loads(row["payload_json"]), "cache"
        with _fetch_lock:
            wait = 1.0 - (time.time() - _last_fetch[0])
            if wait > 0:
                time.sleep(wait)
            try:
                raw = fetcher(code)
            finally:
                _last_fetch[0] = time.time()
        fill_missing(raw)
        if not (raw.get("info") or raw.get("q") or raw.get("a")):
            raise RuntimeError("yfinance tidak mengembalikan data fundamental untuk %s.JK" % code)
        conn.execute("INSERT INTO fundamentals_cache(security_code,fetched_at,payload_json) VALUES(?,?,?) "
                     "ON CONFLICT(security_code) DO UPDATE SET fetched_at=excluded.fetched_at,payload_json=excluded.payload_json",
                     (code, raw["fetched"], json.dumps(raw)))
        conn.commit()
        return raw, "baru"
    except Exception as exc:
        if row:
            return json.loads(row["payload_json"]), "basi: %s" % exc
        raise
    finally:
        conn.close()


# ------------------------------------------------------------------ analisis (fungsi murni, mudah diuji)
def fP(v, d=1, sign=False):
    return "n/a" if v is None else ("%+.*f%%" if sign else "%.*f%%") % (d, v)


def fX(v, d=2):
    return "n/a" if v is None else "%.*fx" % (d, v)


def _pct(new, old):
    return None if new is None or not old else (new - old) / abs(old) * 100


def _yoy(raw, key):
    """pertumbuhan YoY dari kuartal (TTM vs TTM sebelumnya > kuartal vs kuartal sama tahun lalu) lalu tahunan."""
    q = [x[key] for x in raw.get("q", []) if x.get(key) is not None]
    if len(q) >= 8:
        return _pct(sum(q[:4]), sum(q[4:8])), "TTM"
    if len(q) >= 5:
        return _pct(q[0], q[4]), "kuartal"
    a = [x[key] for x in raw.get("a", []) if x.get(key) is not None]
    if len(a) >= 2:
        return _pct(a[0], a[1]), "tahunan"
    return None, None


def _ttm(raw, key):
    q = [x[key] for x in raw.get("q", []) if x.get(key) is not None]
    if len(q) >= 4:
        return sum(q[:4])
    a = [x[key] for x in raw.get("a", []) if x.get(key) is not None]
    return a[0] if a else None


def analyze(raw, price):
    info = raw.get("info", {})
    A = raw.get("a", [])
    sector = (info.get("sector") or "")
    fin = "financial" in sector.lower()
    out = {"name": info.get("longName"), "sector": sector or None, "price": price, "sources": raw.get("src") or ["yfinance"]}

    shares = info.get("sharesOutstanding") or (A[0].get("shares") if A else None)
    mcap = info.get("marketCap") or (price * shares if price and shares else None)
    eps = info.get("trailingEps")
    pe = info.get("trailingPE") or (price / eps if price and eps and eps > 0 else None)
    pb = info.get("priceToBook") or (price / info["bookValue"] if price and info.get("bookValue") else None)
    div12 = raw.get("div12")
    dy = (div12 / price * 100) if (div12 is not None and price) else None
    roe = info.get("returnOnEquity") * 100 if info.get("returnOnEquity") is not None else None
    ttm_ni, ttm_rev = _ttm(raw, "ni"), _ttm(raw, "rev")
    if roe is None and ttm_ni is not None and A and A[0].get("eq"):
        roe = ttm_ni / A[0]["eq"] * 100
    der = None
    if A and A[0].get("debt") is not None and A[0].get("eq"):
        der = A[0]["debt"] / A[0]["eq"]
    elif info.get("debtToEquity") is not None:
        der = info["debtToEquity"] / 100
    margin = info["profitMargins"] * 100 if info.get("profitMargins") is not None else (ttm_ni / ttm_rev * 100 if ttm_ni is not None and ttm_rev else None)
    out["metrics"] = {"mcap": mcap, "pe": pe, "pb": pb, "dy": dy, "roe": roe, "der": der, "eps": eps, "margin": margin}

    ni_yoy, ni_src = _yoy(raw, "ni"); rev_yoy, rev_src = _yoy(raw, "rev")
    out["trend"] = {"ni_yoy": ni_yoy, "rev_yoy": rev_yoy, "src": ni_src or rev_src}

    # --- 8 uji kualitas (True/False/None = tidak dapat dihitung)
    tests = []
    add = lambda label, ok: tests.append({"label": label, "ok": ok})
    add("Laba 12 bln positif", None if ttm_ni is None else ttm_ni > 0)
    add("ROE ≥ COE", None if roe is None else roe >= COE)
    add("Laba tumbuh YoY", None if ni_yoy is None else ni_yoy > 0)
    add("Penjualan tumbuh YoY", None if rev_yoy is None else rev_yoy > 0)
    mg = None
    qq = raw.get("q", [])
    if len(qq) >= 8 and all(x.get("ni") is not None and x.get("rev") for x in qq[:8]):
        m1 = sum(x["ni"] for x in qq[:4]) / sum(x["rev"] for x in qq[:4]); m0 = sum(x["ni"] for x in qq[4:8]) / sum(x["rev"] for x in qq[4:8])
        mg = (m1 - m0) * 100 >= -2
    elif len(A) >= 2 and all(A[i].get("ni") is not None and A[i].get("rev") for i in (0, 1)):
        mg = (A[0]["ni"] / A[0]["rev"] - A[1]["ni"] / A[1]["rev"]) * 100 >= -2
    add("Margin tidak menyusut", mg)
    add("Utang terkendali", None if (fin or der is None) else der < DER_MAX)
    bv = [x["eq"] / x["shares"] for x in A if x.get("eq") and x.get("shares")]
    add("BV/saham naik", (bv[0] > bv[1]) if len(bv) >= 2 else None)
    rys = [x["ni"] / x["eq"] * 100 for x in A if x.get("ni") is not None and x.get("eq")]
    add("ROE stabil multi-tahun", (min(rys[:4]) > 0 and max(rys[:4]) - min(rys[:4]) <= 10) if len(rys) >= 3 else None)
    ev = [t for t in tests if t["ok"] is not None]; passed = sum(1 for t in ev if t["ok"])
    score = round(passed / len(ev) * 100) if len(ev) >= MIN_TESTS else None
    out["tests"] = tests; out["score"] = score; out["passed"] = passed; out["evaluated"] = len(ev)

    # --- skor gabungan (maks 14)
    eps_g = ni_yoy
    def band(v, hi, mid, pts, low_pts, hi_good=True):
        return None
    parts = []
    def part(k, label, val, pts, mx, txt):
        parts.append({"k": k, "label": label, "val": val, "pts": pts, "max": mx, "txt": txt})
    part("roe", "ROE", roe, None if roe is None else 3 if roe > ROE_HI else 2 if roe >= ROE_LO else 0, 3, fP(roe))
    part("pbv", "PBV", pb, None if pb is None else 3 if pb < PBV_VCHEAP else 2 if pb <= PBV_CHEAP else 0, 3, fX(pb))
    part("der", "DER", der, None if (fin or der is None) else 2 if der < DER_OK else 1 if der <= DER_MAX_HARD else -2, 2, fX(der) if not fin else "n/a (keuangan)")
    part("pe", "PE", pe, None if pe is None else 0 if pe <= 0 else 2 if pe < PE_VCHEAP else 1 if pe <= PE_CHEAP else 0, 2, fX(pe, 1))
    part("npm", "NPM", margin, None if margin is None else 2 if margin > NPM_HI else 1 if margin >= NPM_MID else 0, 2, fP(margin))
    part("eps", "EPS YoY", eps_g, None if eps_g is None else 2 if eps_g > EPS_UP else 1 if eps_g >= EPS_FLAT else -1, 2, fP(eps_g, 0, True))
    av = [x for x in parts if x["pts"] is not None]
    raw_total = sum(x["pts"] for x in av); max_av = sum(x["max"] for x in av)
    scaled = round(raw_total / max_av * 14, 1) if len(av) >= MIN_COMPONENTS and max_av else None
    out["score14"] = {"total": scaled, "raw": raw_total, "max_avail": max_av, "parts": parts, "na": [x["label"] for x in parts if x["pts"] is None],
                      "verdict": None if scaled is None else "Mutiara Super" if scaled >= BUY_MIN else "Wajar / Layak Pantau" if scaled >= HOLD_MIN else "Hindari / Risiko Tinggi"}

    # --- kuadran (sumbu Y profitabilitas: ROE & NPM | sumbu X valuasi: PBV & PE)
    prof = None if roe is None else "H" if (roe > ROE_HI and (margin is None or margin > NPM_HI - 5)) else "L" if roe < ROE_LO else "M"
    if pb is None:
        val_ = None
    elif pb < PBV_CHEAP and (pe is not None and 0 < pe < PE_CHEAP):
        val_ = "C"          # murah
    elif pb >= PBV_CHEAP:
        val_ = "E"          # mahal
    else:
        val_ = "M"          # PBV murah tetapi PE tidak mengonfirmasi
    if prof is None or val_ is None:
        quad = ("?", "Data belum cukup", "Tidak dapat menentukan kuadran", "mu")
    elif prof == "H" and val_ == "C":
        quad = ("I", "Kuadran I · Undervalued", "ROE tinggi, harga murah — mutiara terpendam", "up")
    elif prof == "H" and val_ == "E":
        quad = ("II", "Kuadran II · Growth / Premium", "Bagus tapi sudah mahal", "ac")
    elif prof == "L" and pb is not None and pb < PBV_VCHEAP:
        quad = ("III", "Kuadran III · Value Trap", "Murah karena kinerja lesu", "wn")
    elif prof == "L" and val_ == "E":
        quad = ("IV", "Kuadran IV · Overvalued", "Mahal & kinerja rendah", "dn")
    elif prof == "M" and val_ == "C":
        quad = ("I-", "Mendekati Kuadran I", "ROE 10–15%, harga murah", "ac")
    else:
        quad = ("T", "Zona Tengah", "Belum masuk kuadran yang jelas", "mu")
    SHORT = {"I": ("Undervalued", "I", 4), "I-": ("Near Undervalued", "I−", 3), "II": ("Growth / Premium", "II", 3), "III": ("Value Trap", "III", 2),
             "IV": ("Overvalued", "IV", 1), "T": ("Zona Tengah", "–", 2), "?": ("Data kurang", "–", 0)}
    sh = SHORT[quad[0]]
    out["quadrant"] = {"id": quad[0], "title": quad[1], "sub": quad[2], "tone": quad[3], "short": sh[0], "grade": sh[1], "segs": sh[2]}

    # --- sinyal BUY / HOLD / SELL / WAIT (fundamental saja; urutan aturan = prioritas)
    der_ok = fin or der is None or der <= DER_MAX_HARD
    pe_ok = pe is not None and 0 < pe < PE_CHEAP
    checks = [{"label": "Skor ≥ %d" % BUY_MIN, "ok": None if scaled is None else scaled >= BUY_MIN},
              {"label": "Kuadran I", "ok": None if quad[0] == "?" else quad[0] in ("I", "I-")},
              {"label": "DER ≤ %.1fx" % DER_MAX_HARD, "ok": None if (fin or der is None) else der <= DER_MAX_HARD},
              {"label": "PE < %d" % PE_CHEAP, "ok": None if pe is None else pe_ok}]
    neg_ni = ttm_ni is not None and ttm_ni <= 0
    if scaled is None:
        act, why = "WAIT", "data fundamental belum cukup untuk menilai"
    elif neg_ni:
        act, why = "SELL", "laba 12 bulan negatif"
    elif scaled < HOLD_MIN:
        act, why = "SELL", "skor %.1f/14 < %d — hindari / risiko tinggi" % (scaled, HOLD_MIN)
    elif scaled >= BUY_MIN and quad[0] in ("I", "I-") and der_ok and pe_ok:
        act, why = "BUY", "skor %.1f/14, %s, filter DER & PE lolos" % (scaled, quad[1])
    elif scaled >= BUY_MIN:
        act, why = "HOLD", "kualitas bagus (skor %.1f/14) tetapi %s" % (scaled, "tidak murah / PE belum mengonfirmasi" if der_ok else "DER di atas %.1fx" % DER_MAX_HARD)
    elif quad[0] in ("I", "I-", "II"):
        act, why = "HOLD", "skor %.1f/14 wajar, %s" % (scaled, quad[1])
    else:
        act, why = "WAIT", "skor %.1f/14 wajar, %s — pantau dulu" % (scaled, quad[1])
    out["signal"] = {"action": act, "reason": why, "checks": checks}
    out["valuation"] = {"fair_pbv": None, "discount": None, "coe": COE}

    warns = []
    if rev_yoy is not None and rev_yoy < SALES_DROP_WARN:
        warns.append("penjualan turun >%d%% YoY" % abs(SALES_DROP_WARN))
    if ttm_ni is not None and ttm_ni <= 0:
        warns.append("laba 12 bulan negatif")
    if len(rys) >= 3 and roe is not None and rys[0] > 0 and roe > max(rys[1:4]) * 1.3 and roe > sum(rys[1:4]) / len(rys[1:4]) * 1.3:
        warns.append("ROE di puncak siklus — murah bisa menipu")
    if dy is not None and dy > DY_SUSPECT:
        warns.append("dividend yield %.0f%% tidak wajar — cek data/dividen khusus" % dy)
    if der is not None and not fin and der > DER_MAX_HARD:
        warns.append("DER tinggi (%.1fx) — risiko utang" % der)
    if pb is not None and pe is not None and pb < PBV_CHEAP and pe >= 25:
        warns.append("PBV rendah tetapi PE tinggi — laba per saham mungkin anjlok")
    if len(ev) < 8:
        warns.append("data tidak lengkap: %d dari 8 uji dapat dihitung" % len(ev))
    out["warnings"] = warns

    lo, hi = raw.get("low52", info.get("fiftyTwoWeekLow")), raw.get("high52", info.get("fiftyTwoWeekHigh"))
    if lo is not None and hi and hi > lo and price:
        pos = max(0.0, min(100.0, (price - lo) / (hi - lo) * 100))
        out["range52"] = {"low": lo, "high": hi, "pos": pos, "to_high": (hi / price - 1) * 100,
                          "label": "Dekat terendah 52W" if pos < 25 else "Dekat tertinggi 52W" if pos > 75 else "Di tengah rentang"}
    else:
        out["range52"] = None

    rep = info.get("mostRecentQuarter")
    if isinstance(rep, (int, float)):
        rep = datetime.datetime.fromtimestamp(rep, datetime.timezone.utc).strftime("%Y-%m-%d")
    out["report_date"] = rep or (raw["q"][0]["d"] if raw.get("q") else (A[0]["d"] if A else None))
    out["detail"] = {"annual": [{**x, "roe": (x["ni"] / x["eq"] * 100 if x.get("ni") is not None and x.get("eq") else None),
                                 "der": (x["debt"] / x["eq"] if x.get("debt") is not None and x.get("eq") else None)} for x in A[:4]],
                     "quarterly": raw.get("q", [])[:8]}
    return out


# ------------------------------------------------------------------ ringkasan cache & prefetch (agar skor gabungan tersedia di halaman daftar)
def cached_summary():
    """{kode: {t: skor/14, a: sinyal fundamental, q: kuadran, f: waktu ambil}} dari cache SQLite saja (tanpa memanggil yfinance)."""
    out = {}
    conn = database.connect()
    try:
        for r in conn.execute("SELECT security_code,fetched_at,payload_json FROM fundamentals_cache"):
            try:
                a = analyze(json.loads(r[2]), None)
                out[r[0]] = {"t": a["score14"]["total"], "a": a["signal"]["action"], "q": a["quadrant"]["short"], "f": r[1]}
            except Exception:
                continue
    finally:
        conn.close()
    return out


PF = {"q": [], "set": set(), "day": None, "n": 0, "blocked": 0.0, "err": None, "started": False}
PF_DAILY = int(os.environ.get("SCREENER_FUND_DAILY", "120"))     # maks pengambilan baru per hari
PF_GAP = float(os.environ.get("SCREENER_FUND_GAP", "5"))          # jeda antar pengambilan (detik)
_pf_lock = threading.Lock()


def enqueue(codes):
    """Masukkan kode yang cache-nya belum ada/basi ke antrean latar. Mengembalikan jumlah yang ditambahkan."""
    conn = database.connect()
    try:
        fresh = set()
        for r in conn.execute("SELECT security_code,fetched_at FROM fundamentals_cache"):
            try:
                age = (_utcnow() - datetime.datetime.fromisoformat(r[1].rstrip("Z"))).total_seconds() / 3600
                if age < CACHE_HOURS:
                    fresh.add(r[0])
            except Exception:
                pass
    finally:
        conn.close()
    add = 0
    with _pf_lock:
        for c in codes:
            c = str(c).upper()
            if c in fresh or c in PF["set"] or len(PF["q"]) >= 200 or not (2 <= len(c) <= 6 and c.isalnum()):
                continue
            PF["q"].append(c); PF["set"].add(c); add += 1
    return add


def prefetch_status():
    return {"queued": len(PF["q"]), "done_today": PF["n"], "daily_cap": PF_DAILY, "err": PF["err"], "paused": PF["blocked"] > time.time()}


def _pf_loop(fetcher=None):
    while True:
        time.sleep(PF_GAP)
        today = datetime.date.today().isoformat()
        if PF["day"] != today:
            PF["day"], PF["n"] = today, 0
        if PF["blocked"] > time.time() or PF["n"] >= PF_DAILY or not PF["q"]:
            continue
        with _pf_lock:
            c = PF["q"].pop(0); PF["set"].discard(c)
        try:
            get_raw(c) if fetcher is None else get_raw(c, fetcher=fetcher)
            PF["n"] += 1; PF["err"] = None
        except Exception as exc:
            msg = str(exc)
            PF["err"] = msg[:120]
            if any(k in msg.lower() for k in ("too many", "rate", "429")):
                PF["blocked"] = time.time() + 1200       # kena limit -> istirahat 20 menit
                with _pf_lock:
                    PF["q"].insert(0, c); PF["set"].add(c)


def start_prefetch():
    if PF["started"]:
        return
    PF["started"] = True
    threading.Thread(target=_pf_loop, daemon=True, name="fund-prefetch").start()
