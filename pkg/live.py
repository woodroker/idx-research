"""Pengisi harga terbaru dari yfinance ke dataset `px` (kode TANPA .JK, format baris sama persis dgn Ringkasan Saham IDX).

ATURAN PENGAMAN (agar tidak tumpang tindih / tertimpa):
  1. Hanya menyentuh jenis `px`. Data KSEI (days, tipe, sat, kl) dan nama emiten tidak pernah diubah.
  2. Hanya mengisi tanggal LEBIH BARU dari px resmi terakhir (origin bukan 'yfinance'). Tanggal resmi tak pernah ditimpa.
  3. px berasal yfinance diberi origin='yfinance'; saat file Ringkasan IDX tanggal itu diunggah, otomatis digantikan.
  4. Sebelum menulis, dikalibrasi dgn tanggal resmi terakhir (harga & satuan volume). Bila tidak cocok -> batal.
  5. Kolom yang tidak ada di yfinance: foreign buy/sell, frekuensi, bid/offer = 0; nilai transaksi = estimasi vol x (H+L+C)/3;
     saham beredar dibawa dari data resmi terakhir; harga 'sebelumnya' dari penutupan resmi (bukan dari yfinance).
"""
import datetime, json, statistics, threading, time
import database, store

WIB = datetime.timezone(datetime.timedelta(hours=7))
STATE = {"ok": None, "interval": None, "next_run": None, "running": False, "last_run": None, "last_ok": None, "message": "belum dijalankan", "dates": [], "rows": 0}
_lock = threading.Lock()


def now_wib():
    return datetime.datetime.now(WIB)


def market_open(now=None):
    n = now or now_wib()
    return n.weekday() < 5 and datetime.time(8, 55) <= n.time() <= datetime.time(16, 15)


def fetch_daily(codes):
    """-> {kode: {tanggal: [open, high, low, close, volume]}} (bar harian; bar hari ini = berjalan/tertunda)."""
    import yfinance as yf
    out = {}
    for i in range(0, len(codes), 100):
        chunk = [c + ".JK" for c in codes[i:i + 100]]
        df = yf.download(chunk, period="15d", interval="1d", group_by="ticker", progress=False,
                         threads=True, auto_adjust=False)
        for t in chunk:
            try:
                s = df[t].dropna(subset=["Close"])
            except Exception:
                continue
            for idx, r in s.iterrows():
                out.setdefault(t[:-3], {})[idx.strftime("%Y-%m-%d")] = [
                    float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                    float(r["Volume"]) if r["Volume"] == r["Volume"] else 0.0]
    return out


def _load_reference(conn):
    ds = conn.execute("SELECT id,data_date FROM shared_datasets WHERE dataset_type='px' AND origin<>'yfinance' "
                      "ORDER BY data_date DESC LIMIT 1").fetchone()
    if not ds:
        return None, None
    ref = {r[0]: json.loads(r[1]) for r in conn.execute(
        "SELECT security_code,payload_json FROM shared_records WHERE dataset_id=?", (ds["id"],))}
    return ds["data_date"], ref


def _calibrate(ref_date, ref, bars):
    pv, pp = [], []
    for c, a in ref.items():
        b = bars.get(c, {}).get(ref_date)
        if b and len(a) > 2 and a[2] > 0 and b[4] > 0 and a[0] > 0:
            pv.append(b[4] / a[2]); pp.append(b[3] / a[0])
    if len(pv) < 30:
        return None, "kalibrasi gagal: hanya %d saham pembanding pada %s (butuh >=30; tanggal resmi terakhir mungkin >15 hari lalu)" % (len(pv), ref_date)
    mp, mv = statistics.median(pp), statistics.median(pv)
    if not 0.97 <= mp <= 1.03:
        return None, "kalibrasi gagal: harga yfinance vs IDX beda (median rasio %.3f) pada %s" % (mp, ref_date)
    if 0.8 <= mv <= 1.25:
        return 1, None
    if 0.008 <= mv <= 0.0125:
        return 100, None            # yfinance dalam lot -> kali 100 menjadi lembar
    return None, "kalibrasi gagal: satuan volume tidak cocok (median rasio %.4f) pada %s" % (mv, ref_date)


def update(fetcher=fetch_daily, today=None):
    """Satu putaran pembaruan. Aman dipanggil berulang (idempoten). Mengembalikan dict hasil."""
    if not _lock.acquire(blocking=False):
        return {"ok": False, "error": "pembaruan sebelumnya masih berjalan"}
    STATE.update(running=True, last_run=now_wib().isoformat(timespec="seconds"))
    try:
        today = today or now_wib().date().isoformat()
        conn = database.connect()
        try:
            ref_date, ref = _load_reference(conn)
        finally:
            conn.close()
        if not ref_date:
            return _done(False, "Belum ada px resmi (IDX) sebagai acuan. Unggah Ringkasan Saham dulu.")
        codes = [c for c, a in ref.items() if len(a) > 2 and a[2] > 0] or list(ref)
        bars = fetcher(codes)
        if not bars:
            return _done(False, "yfinance tidak mengembalikan data (internet/limit?)")
        scale, err = _calibrate(ref_date, ref, bars)
        if err:
            return _done(False, err)
        new_dates = sorted({d for b in bars.values() for d in b if ref_date < d <= today})
        if not new_dates:
            return _done(True, "tidak ada tanggal baru setelah data resmi %s" % ref_date, ref_date=ref_date)
        chain = {c: a[0] for c, a in ref.items() if a and a[0]}
        items = []
        for d in new_dates:
            data = {}
            for c, b in bars.items():
                if d not in b:
                    continue
                o, h, l, cl, v = b[d]
                v = int(round(v * scale))
                prev = chain.get(c) or o
                cl, prev, o, h, l = (store_round(x) for x in (cl, prev, o, h, l))
                if v <= 0:
                    data[c] = [cl, prev]
                else:
                    listed = ref[c][15] if c in ref and len(ref[c]) > 15 else 0
                    data[c] = [cl, prev, v, int(round(v * (h + l + cl) / 3)), 0, 0, 0, o, h, l, 0, 0, 0, 0, 0, listed, 0]
                chain[c] = cl
            if data:
                items.append({"k": "px", "d": d, "data": data})
        res = store.save_items(items, "yfinance", origin="yfinance", mode="yf")
        c = {}
        for r in res:
            c[r["status"]] = c.get(r["status"], 0) + 1
        return _done(True, "px yfinance: %s" % c, dates=[r["date"] for r in res], rows=sum(r["rows"] for r in res),
                     ref_date=ref_date, detail=res)
    except Exception as exc:
        return _done(False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        STATE["running"] = False
        _lock.release()


def store_round(x):
    x = round(float(x), 2)
    return int(x) if x == int(x) else x


def _done(ok, msg, **extra):
    STATE.update(ok=ok, message=msg, **{k: v for k, v in extra.items() if k in ("dates", "rows")})
    if ok:
        STATE["last_ok"] = now_wib().isoformat(timespec="seconds")
    return dict(ok=ok, **({"message": msg} if ok else {"error": msg}), **{k: v for k, v in extra.items() if k != "detail"})


def start_background(interval=300):
    """Thread latar: tiap `interval` detik selama jam bursa (WIB, Sen-Jum), plus satu kali setelah tutup & saat start."""
    final_done = {"d": None}
    STATE["interval"] = interval

    def loop():
        first = True
        while True:
            n = now_wib()
            after_close = n.weekday() < 5 and n.time() > datetime.time(16, 15) and final_done["d"] != n.date()
            if first or market_open(n) or after_close:
                try:
                    r = update()
                    if after_close and r.get("ok"):
                        final_done["d"] = n.date()
                except Exception:
                    pass
                first = False
            nxt = now_wib() + datetime.timedelta(seconds=interval)
            STATE["next_run"] = (time.time() + interval) if market_open(nxt) else None
            time.sleep(interval)
    threading.Thread(target=loop, daemon=True, name="yf-updater").start()
