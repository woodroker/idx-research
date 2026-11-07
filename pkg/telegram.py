"""Notifikasi Telegram: harga masuk area OTE (sisi beli). Token & chat_id disimpan di telegram.json (TIDAK pernah dikirim ke browser).

PENGAMAN LIMIT / BANNED (semua dapat diubah di telegram.json):
  - Antrean tunggal + jeda minimal min_gap_sec (default 4 dtk) antar pesan  -> jauh di bawah batas Telegram (~1 pesan/dtk per chat).
  - Maks max_per_day pesan per hari (default 20) dan max_burst per kiriman data (default 5); sisanya dibuang, bukan ditumpuk.
  - Satu notifikasi per emiten per hari (per_code_per_day), tercatat di tabel alert_log -> restart server tidak mengulang.
  - Hanya saat bursa buka (WIB) dan hanya data tanggal hari ini (live_only), harga harus benar-benar di dalam zona OTE.
  - HTTP 429: tunggu retry_after (maks 120 dtk) lalu coba sekali lagi. Error 401/403/chat-not-found: notifikasi dimatikan otomatis.
"""
import datetime, json, os, queue, threading, time, urllib.error, urllib.request
from pathlib import Path
import database, fundamentals, live

BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "telegram.json"
DEFAULTS = {"token": "", "chat_id": "", "enabled": False, "market_only": True, "live_only": True,
            "max_per_day": 20, "max_burst": 5, "min_gap_sec": 4, "per_code_per_day": 1}
STATE = {"last_error": None, "last_sent": None, "blocked": False}
Q = queue.Queue()
_pending = set()
_lock = threading.Lock()
_started = [False]


def load_cfg():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if os.environ.get("TELEGRAM_TOKEN"):
        cfg["token"] = os.environ["TELEGRAM_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        cfg["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
    return cfg


def save_cfg(**changes):
    try:
        cur = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur.update(changes)
    CFG_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")


def _http(token, method, payload, timeout=10):
    """Satu panggilan Bot API. -> (status_http, json). Diganti saat pengujian."""
    req = urllib.request.Request("https://api.telegram.org/bot%s/%s" % (token, method), data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"description": str(e)}


HTTP = _http


def _today():
    return live.now_wib().date().isoformat()


def _count_today(kind="ote", status="sent"):
    conn = database.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM alert_log WHERE day=? AND kind=? AND status=?", (_today(), kind, status)).fetchone()[0]
    finally:
        conn.close()


def _code_today(code, kind="ote"):
    conn = database.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM alert_log WHERE day=? AND kind=? AND code=? AND status='sent'", (_today(), kind, code)).fetchone()[0]
    finally:
        conn.close()


def _log(code, price, status, detail="", kind="ote"):
    conn = database.connect()
    try:
        conn.execute("INSERT INTO alert_log(code,kind,day,price,status,detail) VALUES(?,?,?,?,?,?)", (code, kind, _today(), price, status, detail[:300]))
        conn.commit()
    finally:
        conn.close()


def rp(v):
    return "{:,}".format(int(round(float(v)))).replace(",", ".")


def quality_line(code):
    try:
        raw, _ = fundamentals.get_raw(code)
        a = fundamentals.analyze(raw, None)
        t = a["score14"]["total"]
        return "n/a" if t is None else ("%.1f/14 - %s" % (t, a["quadrant"]["short"])).replace(".", ",")
    except Exception:
        return "n/a"


def format_message(it, quality=None):
    return "\n".join(["Emiten: %s" % it["code"],
                      "Status: masuk area OTE - harga sekarang %s" % rp(it["price"]),
                      "Stop: %s" % rp(it["stop"]),
                      "Target TP 1: %s" % rp(it["t1"]),
                      "Target TP 2: %s" % rp(it["t2"]),
                      "Skor kualitas: %s" % (quality if quality is not None else quality_line(it["code"]))])


def configured(cfg=None):
    cfg = cfg or load_cfg()
    return bool(cfg["token"] and str(cfg["chat_id"]).strip())


def status():
    cfg = load_cfg()
    return {"configured": configured(cfg), "enabled": bool(cfg["enabled"]) and configured(cfg) and not STATE["blocked"],
            "want_enabled": bool(cfg["enabled"]), "blocked": STATE["blocked"], "last_error": STATE["last_error"], "last_sent": STATE["last_sent"],
            "sent_today": _count_today(), "max_per_day": cfg["max_per_day"], "queued": Q.qsize()}


def _send_text(cfg, text):
    """-> (ok, fatal, err). Menangani 429 (tunggu retry_after, 1x ulang) dan gangguan jaringan (maks 2 ulang)."""
    tries = 0
    while True:
        tries += 1
        try:
            code, js = HTTP(cfg["token"], "sendMessage", {"chat_id": cfg["chat_id"], "text": text, "disable_web_page_preview": True})
        except Exception as exc:                                  # jaringan putus / timeout
            if tries <= 2:
                time.sleep(5 * tries); continue
            return False, False, "jaringan: %s" % exc
        if js.get("ok"):
            return True, False, None
        desc = str(js.get("description", code))
        if code == 429 and tries <= 2:
            time.sleep(min(int((js.get("parameters") or {}).get("retry_after", 5)) + 1, 120)); continue
        fatal = code in (400, 401, 403, 404) and any(k in desc.lower() for k in ("unauthorized", "forbidden", "chat not found", "blocked", "deactivated", "not found"))
        return False, fatal, "%s %s" % (code, desc)


def enqueue(items):
    """Dipanggil dashboard saat harga emiten berada di dalam zona OTE. Mengembalikan ringkasan (diterima / dilewati + alasan)."""
    cfg = load_cfg(); skipped = {}; ok_n = 0
    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1
    if not configured(cfg) or not cfg["enabled"] or STATE["blocked"]:
        return {"accepted": 0, "skipped": {"notifikasi nonaktif / belum dikonfigurasi": len(items)}}
    if cfg["market_only"] and not live.market_open():
        return {"accepted": 0, "skipped": {"bursa tutup": len(items)}}
    sent = _count_today()
    for it in items:
        try:
            code = str(it["code"]).upper(); price, lo, hi = float(it["price"]), float(it["lo"]), float(it["hi"])
            stop, t1, t2 = float(it["stop"]), float(it["t1"]), float(it["t2"])
        except (KeyError, TypeError, ValueError):
            skip("data tidak lengkap"); continue
        if cfg["live_only"] and str(it.get("date", ""))[:10] != _today():
            skip("data bukan hari ini"); continue
        if not (lo <= price <= hi):
            skip("harga di luar zona OTE"); continue
        if not (stop < price < t1 < t2):
            skip("level stop/target tidak valid"); continue
        with _lock:
            if code in _pending or _code_today(code) >= cfg["per_code_per_day"]:
                skip("sudah dinotifikasi hari ini"); continue
            if sent + Q.qsize() >= cfg["max_per_day"]:
                skip("batas harian tercapai"); continue
            if ok_n >= cfg["max_burst"]:
                skip("batas per kiriman"); continue
            _pending.add(code); Q.put({"code": code, "price": price, "stop": stop, "t1": t1, "t2": t2}); ok_n += 1
    return {"accepted": ok_n, "skipped": skipped}


def _worker():
    while True:
        it = Q.get()
        try:
            cfg = load_cfg()
            if STATE["blocked"] or not cfg["enabled"] or _count_today() >= cfg["max_per_day"] or _code_today(it["code"]) >= cfg["per_code_per_day"]:
                continue
            ok, fatal, err = _send_text(cfg, format_message(it))
            if ok:
                _log(it["code"], it["price"], "sent"); STATE.update(last_sent=live.now_wib().isoformat(timespec="seconds"), last_error=None)
            else:
                _log(it["code"], it["price"], "failed", err or ""); STATE["last_error"] = err
                if fatal:
                    STATE["blocked"] = True              # token salah / bot diblokir: berhenti total, jangan terus mencoba
            time.sleep(max(1.0, float(cfg["min_gap_sec"])))
        except Exception as exc:
            STATE["last_error"] = "%s: %s" % (type(exc).__name__, exc)
        finally:
            _pending.discard(it["code"])


def start():
    if not _started[0]:
        _started[0] = True
        threading.Thread(target=_worker, daemon=True, name="telegram").start()


def send_test():
    cfg = load_cfg()
    if not configured(cfg):
        return {"ok": False, "error": "token/chat_id belum diisi (jalankan: py telegram_setup.py)"}
    ok, fatal, err = _send_text(cfg, "Tes notifikasi screener: koneksi Telegram OK.")
    if fatal:
        STATE["blocked"] = True
    STATE["last_error"] = None if ok else err
    return {"ok": ok, "error": err}


def toggle(enabled):
    cfg = load_cfg()
    if enabled and not configured(cfg):
        return {"ok": False, "error": "token/chat_id belum diisi (jalankan: py telegram_setup.py)"}
    STATE["blocked"] = False if enabled else STATE["blocked"]
    save_cfg(enabled=bool(enabled))
    return {"ok": True, "enabled": bool(enabled)}
