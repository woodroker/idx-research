"""Notifikasi Telegram - detail sinyal trading. Kredensial dibaca dari environment atau telegram.json lokal (TIDAK pernah dikirim ke browser).

Jenis sinyal (fokus BUY):
  REVERSAL        : reversal - Q1 range, Q2 sell-side liquidity sweep/reclaim, Q3/X bullish MSS dan zona entry FVG/OB pada discount.
  MEAN REVERSION  : mr_oversold, mr_bb_reclaim, mr_capitulation; bias D/X bullish + konteks AMD BUY tervalidasi, tidak wajib OTE.
  CALON ARA       : ara_early (pra-breakout), ara_breakout (konfirmasi), ara_potensi (akselerasi), ara_lanjut (ARA tersentuh).
  TOP GAINER BUY  : pre_takeoff_buy - radar top 10% sesi sebelumnya + breakout 20 sesi, aktivitas dan close intraday kuat.
  BREAKOUT/MSS    : breakout, breakout_range, mss, potensi_breakout, potensi_mss.
  TREND/OTE       : trend_pullback, trend_cross, ote, ote_bounce.
  Sinyal gagal OTE tidak lagi diproduksi; sinyal REVERSAL hanya untuk setup BUY terkonfirmasi. Reversal adalah peluang BUY yang terkonfirmasi, bukan peringatan kegagalan.

AMD pada scanner memakai proxy candle harian mingguan: Senin sebagai Q1, Selasa sebagai Q2, Rabu sebagai Q3, Kamis/Jumat sebagai Q4/X. Data harian tidak dapat membuktikan detail M1/M3/M5 intraday; konfirmasi tersebut harus dianggap proxy dan perlu feed intraday untuk akurasi penuh.

MODE KETAT: skor keputusan minimum, kualitas teknikal, likuiditas, risk/reward, batas jarak stop, kuota harian dan kuota per putaran tetap diterapkan. Reversal mempunyai kuota tersendiri dan dikirim ke chat utama dengan detail Entry, SL, TP1, TP2.
Skor keputusan gabungan (-100..+100): teknikal (kekuatan sinyal 0-5) + fundamental (skor 14), lolos bila >= dec_buy dan fundamental bukan SELL.
Sinyal ARA & mean reversion hanya memakai teknikal.

PENGAMAN LIMIT / BANNED (semua dapat diubah di telegram.json):
  - Antrean tunggal + jeda minimal min_gap_sec (default 4 dtk) antar pesan.
  - Maks max_per_day pesan beli per hari, max_per_day_reversal pesan reversal per hari, max_per_day_pot pesan potensi termasuk ARA per hari, max_burst per kiriman; sisanya dibuang.
  - Satu notifikasi per emiten per jenis per hari (per_code_per_day), tercatat di tabel alert_log -> restart server tidak mengulang.
  - Hanya saat bursa buka (WIB) dan hanya data tanggal hari ini (live_only).
  - HTTP 429: tunggu retry_after (maks 120 dtk) lalu coba sekali lagi. Error 401/403/chat-not-found: notifikasi dimatikan otomatis.
"""
import datetime, json, math, os, threading, time, urllib.error, urllib.request
import re
from pathlib import Path
import database, fundamentals, free_float, live
from local_env import load_local_env

BASE = Path(__file__).resolve().parent
CFG_PATH = BASE / "telegram.json"
DEFAULTS = {"token": "", "chat_id": "", "enabled": True, "market_only": True, "live_only": True,
            "max_per_day": 40, "max_burst": 10, "min_gap_sec": 4, "per_code_per_day": 1,
            "kinds": ["pre_takeoff_buy", "four_horsemen", "ara_early", "ara_breakout", "ara_potensi", "ara_lanjut", "breakout", "breakout_range", "mss", "trend_pullback", "trend_cross",
                      "mr_oversold", "mr_bb_reclaim", "mr_capitulation", "reversal", "ote", "ote_bounce", "potensi_breakout", "potensi_mss"],
            "touch_tol_pct": 0.5, "scan_interval_sec": 600, "min_value": 2000000000,
            "min_score": 3, "min_rr": 1.5, "min_stop_pct": 1.0, "max_stop_pct": 8.0, "min_price": 0, "max_chase_pct": 8.0, "one_per_code": True,
            "ara_min_score": 2, "ara_early_min_score": 2.8, "ara_early_min_score100": 56,
            "ara_min_dec": 40, "top_ara_per_scan": 5,
            "ara_breakout_min_score100": 65, "ara_min_value": 500000000, "trend_filter": False, "mr_min_score": 3, "mr_min_rr": 1.2,
            "reversal_min_score": 4.0,  # Model B provisional: 80/100
            "strong_reversal_dec": 85, "top_reversal_per_scan": 3,
            "require_ote": False,
            "max_per_day_reversal": 10, "max_per_day_pot": 30, "pot_dist_pct": 2.0,
            "top_gainer_min_rvol": 1.5, "top_gainer_min_value_ratio": 1.5,
            "top_gainer_min_range_expansion": 1.1, "top_gainer_min_close_position": 0.6,
            "top_gainer_max_chase_pct": 8.0,
            "dec_buy": 30, "w_tech": 0.6, "w_fund": 0.4, "use_fund": True,
            "free_float_risk_enabled": True, "free_float_penalty_per_pp": 1.0,
            "free_float_max_penalty": 10.0, "free_float_urgency_horizon_days": 1095,
            # --- mode ketat (hanya sinyal terkuat) ---
            "strong_dec": 55,        # skor keputusan minimum sinyal beli (di atas dec_buy); sinyal ARA/MR murni teknikal -> otomatis butuh kekuatan >= 3/5
            "pot_min_dec": 50,       # skor keputusan minimum sinyal potensi
            "strong_score": 4,       # kekuatan sinyal minimum (0-5) untuk breakout/MSS/trend/OTE (ARA & mean reversion tidak dikenai)
            "dec_step": 5,           # ambang naik sebesar ini saat kuota harian terpakai >= 50%, dan sekali lagi saat >= 80% (kuota tidak habis di pagi hari)
            "top_per_scan": 5, "top_pot_per_scan": 2}   # hanya N sinyal terkuat yang dikirim per putaran scan
STATE = {"last_error": None, "last_sent": None, "blocked": False, "last_scan": None, "last_signals": 0, "scan_error": None}
# Tidak ada thread/worker yang dimulai saat modul diimpor.
# Antrean disimpan di database agar dapat dibaca oleh proses worker terpisah.
_lifecycle_lock = threading.RLock()
_stop_event = threading.Event()
_sender_thread = None
_scan_thread = None


def load_cfg():
    load_local_env()
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CFG_PATH.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    if os.environ.get("TELEGRAM_TOKEN"):
        cfg["token"] = os.environ["TELEGRAM_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        cfg["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
    # Migrasi konfigurasi lama: kategori peringatan gagal OTE diganti peluang reversal BUY.
    kinds = list(cfg.get("kinds") or DEFAULTS["kinds"])
    if "ote_gagal" in kinds:
        kinds = [k for k in kinds if k != "ote_gagal"]
        if "reversal" not in kinds:
            kinds.append("reversal")
    elif "reversal" not in kinds:
        kinds.append("reversal")
    for required_kind in ("reversal", "ara_early", "ara_breakout", "pre_takeoff_buy", "four_horsemen"):
        if required_kind not in kinds:
            kinds.append(required_kind)
    cfg["kinds"] = kinds
    return cfg


def save_cfg(**changes):
    try:
        cur = json.loads(CFG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cur = {}
    cur.update(changes)
    CFG_PATH.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")


# Satu worker Telegram aktif per database. Lease disimpan di app_meta agar
# tidak membutuhkan tabel baru dan otomatis ikut migrasi skema database.
_WORKER_LEASE_KEY = "telegram_worker_lease"


def acquire_worker_lease(owner, lease_seconds=45):
    """Ambil lease worker secara atomik. False berarti worker lain masih aktif."""
    owner = str(owner or "").strip()
    if not owner:
        raise ValueError("owner worker tidak boleh kosong")
    now = time.time()
    conn = database.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (_WORKER_LEASE_KEY,)).fetchone()
        current = {}
        if row:
            try:
                current = json.loads(row["value"])
            except (TypeError, ValueError):
                current = {}
        try:
            expires_at = float(current.get("expires_at", 0) or 0)
        except (TypeError, ValueError):
            expires_at = 0.0
        if current.get("owner") not in (None, owner) and expires_at > now:
            conn.commit()
            return False
        payload = {"owner": owner, "started_at": current.get("started_at") if current.get("owner") == owner else now,
                   "heartbeat_at": now, "expires_at": now + max(15, int(lease_seconds))}
        conn.execute("INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (_WORKER_LEASE_KEY, json.dumps(payload)))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def renew_worker_lease(owner, lease_seconds=45):
    """Perbarui lease hanya bila proses ini masih menjadi pemiliknya."""
    now = time.time()
    conn = database.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (_WORKER_LEASE_KEY,)).fetchone()
        if not row:
            conn.commit()
            return False
        try:
            current = json.loads(row["value"])
        except (TypeError, ValueError):
            current = {}
        if current.get("owner") != owner:
            conn.commit()
            return False
        current.update(heartbeat_at=now, expires_at=now + max(15, int(lease_seconds)))
        conn.execute("UPDATE app_meta SET value=? WHERE key=?", (json.dumps(current), _WORKER_LEASE_KEY))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release_worker_lease(owner):
    """Lepaskan lease hanya bila masih dimiliki proses pemanggil."""
    conn = database.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (_WORKER_LEASE_KEY,)).fetchone()
        if row:
            try:
                current = json.loads(row["value"])
            except (TypeError, ValueError):
                current = {}
            if current.get("owner") == str(owner):
                conn.execute("DELETE FROM app_meta WHERE key=?", (_WORKER_LEASE_KEY,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def worker_lease_status():
    """Status worker lintas proses; lease kedaluwarsa dianggap offline."""
    conn = database.connect()
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (_WORKER_LEASE_KEY,)).fetchone()
    finally:
        conn.close()
    if not row:
        return {"running": False, "heartbeat_age": None}
    try:
        current = json.loads(row["value"])
        age = max(0.0, time.time() - float(current.get("heartbeat_at", 0)))
        running = float(current.get("expires_at", 0)) > time.time()
        return {"running": running, "heartbeat_age": round(age, 1) if running else None}
    except (TypeError, ValueError, AttributeError):
        return {"running": False, "heartbeat_age": None}


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


# Filter pullback Model B: close maksimal 88% dari high 20 sesi sebelum sinyal.
# Ambang skor default 80/100 masih provisional; validasi ulang dengan cache historis yang lebih panjang.
REV_MAX_HI20 = 0.88
# TP1 reversal dipasang dekat (0.75R) agar winrate tinggi; TP2 = target struktur (High Q1 / min 1.5R).
REV_TP1_R = 0.75
REVERSAL_KINDS = ("reversal", "mr_oversold", "mr_bb_reclaim", "mr_capitulation")
POT_KINDS = ("potensi_breakout", "potensi_mss", "four_horsemen", "ara_early", "ara_breakout", "ara_potensi", "ara_lanjut")  # kandidat/prapemicu; bukan klaim ARA pasti
TOP_GAINER_BUY_KIND = "pre_takeoff_buy"


def _kgrp(kind):
    return "reversal" if kind in REVERSAL_KINDS else "pot" if kind in POT_KINDS else "buy"


def _cap(cfg, g):
    return int(cfg["max_per_day"] if g == "buy" else cfg.get("max_per_day_" + g, cfg.get("max_per_day_reversal", 10)))


def _count_today(kind=None, status="sent", group=None):
    """Jumlah notif hari ini. group: 'buy' (sinyal beli terkonfirmasi), 'pot' (kandidat/potensi termasuk ARA), None -> semua."""
    q = "SELECT COUNT(*) FROM alert_log WHERE day=? AND status=?"; p = [_today(), status]
    if kind is not None:
        q += " AND kind=?"; p.append(kind)
    if group in ("reversal", "pot"):
        ks = REVERSAL_KINDS if group == "reversal" else POT_KINDS
        q += " AND kind IN (%s)" % ",".join("?" * len(ks)); p += list(ks)
    elif group == "buy":
        ks = REVERSAL_KINDS + POT_KINDS
        q += " AND kind NOT IN (%s)" % ",".join("?" * len(ks)); p += list(ks)
    conn = database.connect()
    try:
        return conn.execute(q, p).fetchone()[0]
    finally:
        conn.close()


def _queued(group=None):
    """Jumlah pekerjaan Telegram yang masih menunggu/diproses di database hari ini."""
    conn = database.connect()
    try:
        sql = "SELECT COUNT(*) FROM telegram_outbox WHERE day=? AND status IN ('pending','processing')"
        params = [_today()]
        if group == "reversal":
            sql += " AND kind IN (%s)" % ",".join("?" * len(REVERSAL_KINDS))
            params.extend(REVERSAL_KINDS)
        elif group == "pot":
            sql += " AND kind IN (%s)" % ",".join("?" * len(POT_KINDS))
            params.extend(POT_KINDS)
        elif group == "buy":
            excluded = REVERSAL_KINDS + POT_KINDS
            sql += " AND kind NOT IN (%s)" % ",".join("?" * len(excluded))
            params.extend(excluded)
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


# ---------- riwayat sinyal terkirim hari ini (untuk tab SINYAL HARI INI di dashboard) ----------
SIG_PATH = BASE / "signals_today.json"
_SIG = {"day": None, "items": [], "last_scan": None}
_sig_lock = threading.Lock()


def _sig_valid_items(items):
    """Buang artefak riwayat yang tidak punya kode/jenis sinyal; jangan tampilkan kartu tanpa identitas."""
    return [x for x in items if isinstance(x, dict) and str(x.get("code") or "").strip()
            and str(x.get("kind") or "").strip()]


def _sig_load():
    try:
        d = json.loads(SIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    if d.get("day") == _today():
        source_items = d.get("items")
        raw_items = source_items if isinstance(source_items, list) else []
        clean_items = _sig_valid_items(raw_items)
        _SIG.update(day=d["day"], items=clean_items, last_scan=d.get("last_scan"))
        if source_items != clean_items:
            try:
                SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
    else:
        _SIG.update(day=_today(), items=[], last_scan=None)
    for x in _SIG["items"]:                                   # sinyal hari ini yang sudah ada ikut masuk riwayat (tanpa duplikat)
        _hist_add(dict(x, day=_SIG["day"]))


def _sig_reload():
    """Muat riwayat hari ini dari file (worker & server = proses berbeda; hapus kartu dari server harus terlihat oleh worker)."""
    try:
        d = json.loads(SIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _SIG.update(day=_today(), items=[], last_scan=None)
        return
    if d.get("day") == _today():
        source_items = d.get("items")
        raw_items = source_items if isinstance(source_items, list) else []
        clean_items = _sig_valid_items(raw_items)
        _SIG.update(day=d["day"], items=clean_items, last_scan=d.get("last_scan"))
        if source_items != clean_items:
            try:
                SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
    else:
        _SIG.update(day=_today(), items=[], last_scan=None)


def _sig_update_now(prices):
    """Simpan harga terakhir per kode ke riwayat sinyal hari ini (field 'now') agar kartu bisa menggambar ekor naik/turun."""
    with _sig_lock:
        _sig_reload()
        changed = False
        for x in _SIG["items"]:
            p = prices.get(str(x.get("code", "")).upper())
            if p and x.get("now") != p:
                x["now"] = p; changed = True
        if changed:
            try:
                SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass


def delete_signal(code, kind, time_=None):
    """Hapus satu sinyal dari riwayat hari ini + riwayat akurasi. alert_log sengaja TIDAK disentuh agar sinyal yang sama tidak terkirim ulang / kuota tidak kacau."""
    code = str(code or "").upper(); kind = str(kind or "")
    with _sig_lock:
        _sig_reload()
        if _SIG["day"] != _today():
            _SIG.update(day=_today(), items=[])
        keep = [x for x in _SIG["items"] if not (str(x.get("code", "")).upper() == code and x.get("kind") == kind
                                                 and (time_ in (None, "") or x.get("time") == time_))]
        removed = len(_SIG["items"]) - len(keep)
        _SIG["items"] = keep
        try:
            SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        day = _SIG["day"]
    with _hist_lock:
        items = _hist_read()
        left = [x for x in items if not (x.get("day") == day and str(x.get("code", "")).upper() == code and x.get("kind") == kind)]
        if len(left) != len(items):
            try:
                HIST_PATH.write_text(json.dumps({"items": left}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
    _STATS["data"] = None
    return {"ok": True, "removed": removed}


def _sig_add(it):
    with _sig_lock:
        if _SIG["day"] != _today():
            _SIG.update(day=_today(), items=[])
        _sig_reload()
        row = {k: it.get(k) for k in ("code", "kind", "price", "stop", "t1", "t2", "score", "dec", "dec_raw", "dec_adjusted", "free_float_penalty", "free_float_gap_pp", "free_float_current_pct", "free_float_required_pct", "free_float_deadline", "free_float_deadline_status", "free_float_as_of", "free_float_source", "ote", "lo", "hi", "trig", "ref", "fase", "phase", "entry_lo", "entry_hi", "entry_source", "true_open", "q1_high", "q1_low", "sweep_low", "amd_reasons", "amd_context", "reversal_score", "amd_quality_score", "amd_score_detail", "vratio", "ara_score", "ara_stage", "ara_price", "ara_reasons", "relative_volume", "projected_value", "turnover_float",
                "foreign_flow_ratio_5d", "foreign_flow_coverage_days", "foreign_flow_asof",
                "top_gainer_score", "top_gainer_candidate", "top_gainer_rank", "top_gainer_universe",
                "top_gainer_asof", "top_gainer_reasons", "scan_time", "pre_takeoff_factors",
                "pre_takeoff_relative_volume", "pre_takeoff_relative_value", "pre_takeoff_range_expansion",
                "pre_takeoff_close_position", "pre_takeoff_return_pct", "pre_takeoff_data_source", "pre_takeoff_signal",
                "four_horsemen_factors", "four_horsemen_rules", "four_horsemen_confirmation")}
        row["time"] = live.now_wib().strftime("%H:%M")
        _SIG["items"].append(row)
        try:
            SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        _hist_add(dict(row, day=_SIG["day"]))


def signals_today():
    """Sinyal yang SUDAH terkirim ke Telegram hari ini -> dipakai endpoint /api/telegram/signals."""
    with _sig_lock:
        _sig_reload()
        if _SIG["day"] != _today():
            _SIG.update(day=_today(), items=[], last_scan=None)
        return {"ok": True, "day": _SIG["day"], "last_scan": _SIG.get("last_scan"), "items": list(_SIG["items"])}


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


# ---------- fase AMDX (port PPH di app.js: siklus mingguan, data harian) ----------
_PH = {"A": "Accumulation", "M": "Manipulation", "D": "Distribution", "XC": "X Continuation", "XR": "X Reversal"}


def _amdx(cs):
    """-> teks fase candle terakhir, mis. 'Distribution ?'. Sen=A, Sel=M, Rab=D, Kam-Jum=X. None bila data kurang."""
    n = len(cs)
    if n < 5:
        return None
    B = [{"d": str(x["date"])[:10], "o": float(x["open"] or x["close"]), "h": float(x["high"]), "l": float(x["low"]), "c": float(x["close"])} for x in cs]
    atr = []; s_ = 0.0
    for i, b in enumerate(B):                                         # ATR Wilder 14, sama dengan PATR
        tr = max(b["h"] - b["l"], abs(b["h"] - B[i - 1]["c"]), abs(b["l"] - B[i - 1]["c"])) if i else b["h"] - b["l"]
        if i < 14:
            s_ += tr; atr.append(s_ / (i + 1))
        else:
            atr.append((atr[i - 1] * 13 + tr) / 14)
    sgn = lambda v, t: 1 if v > t else -1 if v < -t else 0
    def wk(d):
        t = datetime.date.fromisoformat(d); return t.toordinal() - t.weekday()
    ws = 0; wd = 0; p = dr = None
    for i in range(n):
        w = datetime.date.fromisoformat(B[i]["d"]).isoweekday()
        if i == 0 or wk(B[i]["d"]) != wk(B[i - 1]["d"]):
            ws = i; wd = 0
        a = atr[i] or 1; o0 = B[ws]["o"]; net = (B[i]["c"] - o0) / a; mv = (B[i]["c"] - B[i - 1]["c"]) / a if i else 0
        if w == 1:
            p = "A"; dr = sgn(B[i]["c"] - B[i]["o"], 0)
        elif w == 2:
            p = "M"; pv = B[i - 1] if i > ws else B[i]
            up = B[i]["h"] > pv["h"]; dn = B[i]["l"] < pv["l"]
            dr = -1 if up and not dn else 1 if dn and not up else -sgn(B[i]["c"] - B[i]["o"], 0)
        elif w == 3:
            p = "D"; dr = sgn(net, .15) or sgn(mv, 0); wd = dr
        else:
            if not wd:
                for j in range(i - 1, ws - 1, -1):
                    nj = (B[j]["c"] - o0) / (atr[j] or 1)
                    if abs(nj) > .15:
                        wd = sgn(nj, 0); break
            m = sgn(mv, 0)
            if wd and m and m != wd:
                p = "XR"; dr = m
            else:
                p = "XC"; dr = wd or m
    return _PH[p] + (" \u2197" if dr > 0 else " \u2198" if dr < 0 else "")


def _amx(cs):
    """BUY context AMD terkonfirmasi: Q1 range, Q2 sweep/reclaim, Q3/X bullish reclaim/MSS dan phase mengarah naik."""
    return bool(_amd_buy_context(cs).get("valid"))


# ---------- umpan skor dashboard (sama dengan kolom Keputusan di tabel) ----------
_DASH = {"day": None, "rows": {}, "updated_at": None}
_DASH_META_KEY = "dashboard_decision_snapshot"
_DASH_CACHE_AT = 0.0
_DASH_LOCK = threading.RLock()


def set_dash(rows):
    """Simpan skor KEP dashboard ke app_meta agar Flask dan Telegram Worker berbagi snapshot."""
    global _DASH_CACHE_AT
    day = _today(); out = {}
    for c, v in (rows or {}).items():
        try:
            phase = str(v.get("phase") or "")[:2].upper() or None
            if phase not in ("A", "M", "D", "XC", "XR"):
                phase = None
            phase_dir = v.get("phase_dir")
            phase_dir = int(phase_dir) if phase_dir in (-1, 0, 1, "-1", "0", "1") else None
            out[str(c).upper()] = {
                "K": None if v.get("K") is None else float(v["K"]),
                "act": str(v.get("act") or ""),
                "phase": phase,
                "phase_dir": phase_dir,
                "amdx_buy": bool(v.get("amdx_buy")),
            }
        except (AttributeError, TypeError, ValueError):
            continue
    payload = {"day": day, "updated_at": time.time(), "rows": out}
    conn = database.connect()
    try:
        conn.execute("INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                     (_DASH_META_KEY, json.dumps(payload, separators=(",", ":"))))
        conn.commit()
    finally:
        conn.close()
    with _DASH_LOCK:
        _DASH.update(day=day, rows=out, updated_at=payload["updated_at"])
        _DASH_CACHE_AT = time.time()
    return {"ok": True, "n": len(out)}


def _dash_snapshot():
    """Muat snapshot terbaru lintas proses; cache pendek agar tidak SELECT per ticker."""
    global _DASH_CACHE_AT
    now = time.time()
    with _DASH_LOCK:
        if _DASH.get("day") == _today() and now - _DASH_CACHE_AT <= 5:
            return _DASH
    conn = database.connect()
    try:
        row = conn.execute("SELECT value FROM app_meta WHERE key=?", (_DASH_META_KEY,)).fetchone()
    finally:
        conn.close()
    snapshot = {"day": None, "rows": {}, "updated_at": None}
    if row:
        try:
            raw = json.loads(row["value"])
            updated_at = float(raw.get("updated_at", 0))
            age = now - updated_at
            if raw.get("day") == _today() and 0 <= age <= 900 and isinstance(raw.get("rows"), dict):
                snapshot = {"day": raw["day"], "rows": raw["rows"], "updated_at": updated_at}
        except (TypeError, ValueError, AttributeError):
            pass
    with _DASH_LOCK:
        _DASH.update(snapshot)
        _DASH_CACHE_AT = now
        return _DASH


def _dash(code):
    snap = _dash_snapshot()
    return snap["rows"].get(str(code).upper()) if snap["day"] == _today() else None


def dashboard_snapshot():
    """Snapshot keputusan dashboard untuk UI alternatif; stale snapshot dikosongkan."""
    snap = _dash_snapshot()
    if snap.get("day") != _today() or not snap.get("updated_at"):
        return {"day": None, "rows": {}, "updated_at": None}
    cfg = load_cfg()
    rows = {}
    for code, original in (snap.get("rows") or {}).items():
        row = dict(original)
        raw = row.get("K")
        ff = free_float.risk_context(
            code, today=_today(), enabled=cfg.get("free_float_risk_enabled", True),
            penalty_per_pp=cfg.get("free_float_penalty_per_pp", 1.0),
            max_penalty=cfg.get("free_float_max_penalty", 10.0),
            urgency_horizon_days=cfg.get("free_float_urgency_horizon_days", 1095))
        penalty = (min(float(raw), max(0.0, float(ff.get("penalty", 0.0))))
                   if raw is not None and float(raw) > 0 else 0.0)
        row["raw_K"] = raw
        row["free_float_penalty"] = penalty
        row["free_float"] = ff
        if raw is not None:
            row["K"] = max(-100.0, float(raw) - penalty)
            if row.get("act") == "BUY" and row["K"] < float(cfg.get("dec_buy", 30)):
                row["act"] = "HOLD"
        rows[code] = row
    return {"day": snap.get("day"), "rows": rows,
            "updated_at": snap.get("updated_at")}


# ---------- skor keputusan gabungan ----------
POT_DIST_PCT = [DEFAULTS["pot_dist_pct"]]   # diisi ulang dari cfg tiap scan()
_FUND = {}      # (hari, kode) -> (skor fundamental -100..+100, aksi fundamental)


def _fund_z(code):
    """Skor fundamental -100..+100 (sama dengan fundZ di app.js) + aksi BUY/HOLD/WAIT/SELL. Di-cache per hari."""
    day = _today(); key = (day, code)
    if key not in _FUND:
        for k in [k for k in _FUND if k[0] != day]:
            del _FUND[k]
        try:
            raw, _ = fundamentals.get_raw(code)
            a = fundamentals.analyze(raw, None)
            t = a["score14"]["total"]
            z = None if t is None else max(-100.0, min(100.0, (t - 7) / 7.0 * 100.0))
            act = (a.get("signal") or {}).get("action")
        except Exception:
            z, act = None, None
        _FUND[key] = (z, act)
    return _FUND[key]


def decision(it, cfg):
    """Skor keputusan; reversal/MR harus lolos konteks AMD BUY dan bias bullish."""
    kind = str(it.get("kind", ""))
    if kind == TOP_GAINER_BUY_KIND:
        tech = max(0.0, min(5.0, float(it.get("score") or 0))) / 5.0 * 100.0
        return tech, tech >= float(cfg.get("dec_buy", 30))
    if kind == "four_horsemen":
        tech = max(0.0, min(5.0, float(it.get("score") or 0))) / 5.0 * 100.0
        return tech, tech >= float(cfg.get("dec_buy", 30))
    if kind == "reversal" and not it.get("ax"):
        t = max(0.0, min(5.0, float(it.get("score") or 0))) / 5.0 * 100.0
        return t, False
    if kind.startswith("mr_") and not it.get("amd_phase_bullish"):
        t = max(0.0, min(5.0, float(it.get("score") or 0))) / 5.0 * 100.0
        return t, False
    d = None if kind.startswith(("ara", "mr_")) or kind in REVERSAL_KINDS else _dash(it["code"])
    if d and d["K"] is not None:
        it["_src"] = "dash"
        return d["K"], d["act"] == "BUY"
    t = max(0.0, min(5.0, float(it.get("score") or 0))) / 5.0 * 100.0
    if not kind.startswith("ara") and not it.get("ax"):
        return t, False
    tech_only = kind.startswith(("ara", "mr_")) or kind in REVERSAL_KINDS or not cfg.get("use_fund", True)
    fz, fact = (None, None) if tech_only else _fund_z(it["code"])
    wt, wf = float(cfg["w_tech"]), float(cfg["w_fund"])
    K = t if fz is None else (wt * t + wf * fz) / (wt + wf)
    return K, (fact != "SELL" and K >= float(cfg["dec_buy"]))


def _min_dec(cfg, base, group):
    """Ambang skor keputusan naik bertahap saat kuota harian grup terpakai, supaya kuota tidak habis di pagi hari."""
    try:
        used = (_count_today(group=group) + _queued(group)) / float(max(1, _cap(cfg, group)))
    except Exception:
        used = 0.0
    step = float(cfg.get("dec_step", 5))
    return float(base) + (step if used >= 0.5 else 0.0) + (step if used >= 0.8 else 0.0)


def apply_decision(items, cfg):
    """Urutkan BUY, REVERSAL BUY, dan POTENSI dengan kuota masing-masing."""
    buys, reversals, pots, aras, horsemen = [], [], [], [], []
    min_buy = _min_dec(cfg, cfg.get("strong_dec", 55), "buy")
    min_pot = _min_dec(cfg, cfg.get("pot_min_dec", 50), "pot")
    min_rev = _min_dec(cfg, cfg.get("strong_reversal_dec", 65), "reversal")
    for it in items:
        K, ok = decision(it, cfg)
        if not ok:
            continue
        kind = it["kind"]
        pot = kind in POT_KINDS
        rev = kind in REVERSAL_KINDS
        dsh = it.get("_src") == "dash"
        threshold = min_rev if rev else float(cfg.get("dec_buy", 30)) if kind == "four_horsemen" else min_pot if pot else min_buy
        if kind.startswith("ara"):                       # ARA: ambang & kuota per putaran sendiri, tidak berebut dengan potensi breakout/MSS
            threshold = float(cfg.get("ara_min_dec", 40))
        elif dsh:
            threshold = _min_dec(cfg, cfg["dec_buy"], "pot" if pot else "buy")
        raw_K = K
        ff = free_float.risk_context(
            it.get("code"), today=_today(), enabled=cfg.get("free_float_risk_enabled", True),
            penalty_per_pp=cfg.get("free_float_penalty_per_pp", 1.0),
            max_penalty=cfg.get("free_float_max_penalty", 10.0),
            urgency_horizon_days=cfg.get("free_float_urgency_horizon_days", 1095))
        it["dec_raw"] = raw_K
        it["free_float_penalty"] = 0.0
        it["free_float_gap_pp"] = ff.get("gap_pp")
        it["free_float_current_pct"] = ff.get("current_pct")
        it["free_float_required_pct"] = ff.get("required_pct")
        it["free_float_deadline"] = ff.get("deadline")
        it["free_float_deadline_status"] = ff.get("deadline_status")
        it["free_float_as_of"] = ff.get("as_of")
        it["free_float_source"] = ff.get("source")
        if not pot and raw_K is not None:
            penalty = min(max(0.0, raw_K), max(0.0, float(ff.get("penalty", 0.0))))
            K = max(-100.0, raw_K - penalty)
            it["free_float_penalty"] = penalty
        it["dec_adjusted"] = K
        if K < threshold:
            continue
        if not (pot or rev) and not kind.startswith("ara") and kind not in REVERSAL_KINDS and (it.get("score") or 0) < cfg.get("strong_score", 4):
            continue
        it["dec"] = K
        (horsemen if kind == "four_horsemen" else aras if kind.startswith("ara") else pots if pot else reversals if rev else buys).append(it)
    for lst in (buys, reversals, pots, aras, horsemen):
        lst.sort(key=lambda x: (-x["dec"], -x.get("_val", 0)))
    return (reversals[:int(cfg.get("top_reversal_per_scan", 3))] +
            aras[:int(cfg.get("top_ara_per_scan", 5))] + buys[:int(cfg.get("top_per_scan", 5))] +
            pots[:int(cfg.get("top_pot_per_scan", 2))] + horsemen[:int(cfg.get("max_burst", 10))])


# ---------- teks pesan ----------
LABEL = {"ara_early": "DETEKSI DINI ARA - pra-breakout sebelum akselerasi harga",
         "ara_breakout": "BREAKOUT ARA TERKONFIRMASI - close melewati resistance dengan volume",
         "ara_potensi": "AKSELERASI MENUJU ARA - momentum mulai mendekati batas ARA",
         "ara_lanjut": "ARA TERSENTUH - kandidat lanjut ARA besok (TP1 = ARA besok)",
         "breakout": "BREAKOUT high 20 hari", "breakout_range": "BREAKOUT dari konsolidasi 10 hari (volume ok)",
         "mss": "MSS bullish (tembus high kemarin)",
         "trend_pullback": "TREND FOLLOWING - pullback ke EMA20 lalu naik lagi", "trend_cross": "TREND FOLLOWING - EMA20 cross up EMA50",
         "mr_oversold": "MEAN REVERSION - oversold & mulai memantul",
         "mr_bb_reclaim": "MEAN REVERSION - kembali masuk Bollinger bawah",
         "mr_capitulation": "MEAN REVERSION - capitulation + hammer (volume besar)",
         TOP_GAINER_BUY_KIND: "TOP GAINER BUY - radar sesi sebelumnya + breakout 20 sesi dan ekspansi aktivitas",
         "four_horsemen": "POTENSI 4 HORSEMEN - salah satu atau kedua aturan FVG/EMA20 terpenuhi",
         "potensi_breakout": "POTENSI BREAKOUT - mendekati resistance, belum tembus",
         "potensi_mss": "POTENSI MSS - mendekati high kemarin, belum tembus",
         "ote": "menyentuh area OTE", "ote_bounce": "baru saja OTE - retrace lalu lanjut naik",
         "reversal": "AMD REVERSAL BUY - Q2 liquidity sweep/reclaim, bullish MSS, entry discount FVG/OB",
         "momentum": "momentum naik masih kuat", "bullish": "candle bullish kuat"}
GRUP = {"breakout": "BREAKOUT", "breakout_range": "BREAKOUT", "mss": "MSS", TOP_GAINER_BUY_KIND: "TOP GAINER BUY", "trend_pullback": "TREND FOLLOWING", "trend_cross": "TREND FOLLOWING",
        "ote": "OTE", "ote_bounce": "OTE", "reversal": "REVERSAL", "potensi_breakout": "POTENSI BREAKOUT", "potensi_mss": "POTENSI MSS"}
OTE_TXT = {"sentuh": "MENYENTUH area OTE", "baru": "BARU SAJA OTE (retrace lalu naik lagi)"}


def _grup(kind):
    if kind == "ara_early":
        return "PRE-ARA"
    return "CALON ARA" if kind.startswith("ara") else "MEAN REVERSION" if kind.startswith("mr_") else GRUP.get(kind, "SINYAL BELI")


TIERS = ((75, "\U0001F525", "SANGAT KUAT"), (65, "\U0001F7E2", "KUAT"), (55, "\U0001F7E1", "CUKUP"), (-1e9, "\u26AA", "STANDAR"))   # ?? ?? ?? ?


def tier(it):
    """-> (emoji, label, skor) menurut skor keputusan (atau kekuatan sinyal bila skor keputusan belum ada); None bila tak ada skor."""
    k = it.get("dec")
    if k is None and it.get("score") is not None:
        k = float(it["score"]) / 5.0 * 100.0
    if k is None:
        return None
    for lim, em, lb in TIERS:
        if k >= lim:
            return em, lb, k


KET = {"ara_early": "Pra-breakout: akumulasi, turnover, volume relatif, dan resistance berkonfluensi",
       "ara_breakout": "Breakout terkonfirmasi di atas resistance, volume dan likuiditas mendukung",
       "ara_potensi": "Momentum meningkat, kandidat menuju ARA hari ini", "ara_lanjut": "Batas ARA tersentuh/terdekat; bukan jaminan ARA berikutnya",
       "breakout": "Penerusan - tembus high 20 hari", "breakout_range": "Penerusan - keluar konsolidasi 10 hari",
       "mss": "Reversal - tembus high kemarin", "trend_pullback": "Pullback ke EMA20", "trend_cross": "Penerusan - EMA20 cross up EMA50",
       "mr_oversold": "Reversal - oversold memantul", "mr_bb_reclaim": "Reversal - kembali masuk Bollinger bawah",
       "mr_capitulation": "Reversal - capitulation + hammer", "ote": "Pullback - menyentuh zona OTE", "ote_bounce": "Pullback - OTE lalu naik lagi",
       "momentum": "Penerusan - momentum kuat", "bullish": "Candle bullish kuat",
        TOP_GAINER_BUY_KIND: "Radar Top Gainer sesi sebelumnya + breakout 20 sesi; volume/value dan candle berjalan menguat (provisional)",
        "four_horsemen": "Satu atau dua aturan bullish 4 Horsemen terdeteksi; MSS/BOS, reversal, dan ekspansi aktivitas menaikkan prioritas",
       "potensi_breakout": "Mendekati resistance, belum tembus", "potensi_mss": "Mendekati high kemarin, belum tembus",
       "reversal": "Reversal BUY - Q2 sweep/reclaim dan Q3/X bullish MSS"}


STATUS_EMOJI = {"REVERSAL": "\U0001F504", "BREAKOUT ARA": "\U0001F680", "ARA TERSENTUH": "\U0001F680",
                "PRE-ARA": "\U0001F440", "MENUJU ARA": "\U0001F440", "POTENSI ARA": "\U0001F440",
                "POTENSI": "\U0001F50D", "BELI": "\u2705"}


def _status(it):
    """Status singkat: BELI / REVERSAL / POTENSI ARA dst (tanpa kode & skor)."""
    kind = str(it.get("kind", "ote"))
    if kind in REVERSAL_KINDS:
        return "REVERSAL"
    if kind == "ara_breakout":
        return "BREAKOUT ARA"
    if kind == "ara_lanjut":
        return "ARA TERSENTUH"
    if kind == "ara_early":
        return "PRE-ARA"
    if kind == "ara_potensi":
        return "MENUJU ARA"
    if kind.startswith("ara"):
        return "POTENSI ARA"
    if kind == "four_horsemen":
        return "POTENSI"
    if kind in POT_KINDS:
        return "POTENSI"
    return "BELI"


def _head(it):
    """Header satu baris: KODE - BELI / REVERSAL / POTENSI ARA."""
    code = str(it.get("code") or "").strip().upper() or "EMITEN"
    status = _status(it)
    k = it.get("dec")
    if k is None and it.get("score") is not None:
        k = float(it["score"]) / 5.0 * 100.0
    score = " · skor %+d" % round(k) if k is not None else ""
    return "%s - %s%s" % (code, status, score)


def format_message(it, quality=None):
    """Pesan Telegram ala kartu: emoji STATUS - KODE (skor), OTE Buy/Sell, Stop/TP1/TP2, Fase, Status."""
    kind = str(it.get("kind", "ote"))
    code = str(it.get("code") or "").strip().upper()
    status = _status(it)
    k = it.get("dec")
    if k is None and it.get("score") is not None:
        k = float(it["score"]) / 5.0 * 100.0
    score = " · skor %+d" % round(k) if k is not None else ""
    emoji = STATUS_EMOJI.get(status, "\u2705")

    L = ["%s %s - %s%s" % (emoji, status, code or "EMITEN", score)]
    if it.get("top_gainer_score") is not None:
        radar="Radar Top Gainer: %.0f/100"%float(it["top_gainer_score"])
        if it.get("top_gainer_candidate"): radar+=" · 10% teratas"
        L.append(radar)
        why=it.get("top_gainer_reasons") or []
        if why: L.append("Faktor: "+" · ".join(str(x) for x in why[:3]))
    if kind == TOP_GAINER_BUY_KIND:
        L.append("Harga referensi BUY: %s (snapshot intraday; bar harian masih berjalan)" % rp(it["price"]))
        factors = it.get("pre_takeoff_factors") or []
        if factors:
            L.append("Pola: " + " · ".join(str(x) for x in factors))
    elif kind == "four_horsemen":
        L.append("Harga pantau: %s (candle harian berjalan)" % rp(it["price"]))
        factors = it.get("four_horsemen_factors") or []
        if factors:
            L.append("Pola: " + " · ".join(str(x) for x in factors))
    else:
        side = "Sell" if float(it["t1"]) < float(it["price"]) else "Buy"        # bias arah dari posisi target terhadap harga
        L.append("OTE %s: %s" % (side, rp(it["price"])))
    L.extend(["Stop: %s" % rp(it["stop"]), "TP1: %s" % rp(it["t1"]), "TP2: %s" % rp(it["t2"])])
    if kind in (TOP_GAINER_BUY_KIND, "four_horsemen"):
        risk_per_share = max(0.0, float(it["price"]) - float(it["stop"]))
        L.append("Risiko harga: %s per saham." % rp(risk_per_share))
    if it.get("free_float_penalty", 0) > 0 and it.get("dec_raw") is not None:
        L.append("Skor keputusan: %+d → %+d (dasar %+d; penalti free float −%.1f poin; heuristik)." %
                 (round(float(it["dec_raw"])), round(float(it.get("dec_adjusted", it.get("dec", 0)))),
                  round(float(it["dec_raw"])), float(it["free_float_penalty"])))

    if kind in REVERSAL_KINDS:
        if it.get("entry_lo") is not None and it.get("entry_hi") is not None:
            L.append("Zona entry %s: %s - %s" % (it.get("entry_source", "FVG/OB"), rp(it["entry_lo"]), rp(it["entry_hi"])))
    if kind in POT_KINDS and it.get("trig"):
        delta = (float(it["trig"]) / float(it["price"]) - 1) * 100 if float(it["price"]) else 0.0
        if kind == "ara_breakout":
            L.append("Konfirmasi: close sudah di atas resistance %s" % rp(it["trig"]))
        elif kind == "four_horsemen" and delta <= 0:
            L.append("Konfirmasi harga: sudah melewati high pola %s" % rp(it["trig"]))
        else:
            L.append("Trigger: tembus %s (+%.1f%%)" % (rp(it["trig"]), delta))
    if kind.startswith("ara") and it.get("ara_price") is not None:
        L.append("Batas ARA indikatif: %s" % rp(it["ara_price"]))
        if it.get("ara_board_assumed"):
            L.append("Asumsi papan Utama/Pengembangan/Ekonomi Baru; status papan belum diverifikasi.")
        L.append("Acuan aturan BEI efektif 28-09-2026.")
        snap = it.get("bid_offer_snapshot")
        if snap:
            L.append("Snapshot bid/offer %s: %s/%s (%.2fx); data harian, bukan antrean intraday." %
                     (snap.get("date"), rp(snap.get("bid_volume")), rp(snap.get("offer_volume")), snap.get("ratio", 0)))

    if kind in ("ara_early","ara_breakout") and it.get("ara_score") is not None:
        L.append("Skor %s: %.0f/100 (heuristik, bukan probabilitas)." %
                 ("Pre-ARA" if kind=="ara_early" else "Breakout ARA",float(it["ara_score"])))
        ara_reasons=it.get("ara_reasons") or []
        if ara_reasons: L.append("Komponen: "+" · ".join(str(x) for x in ara_reasons[:5]))
    fase = it.get("fase") or it.get("phase")
    if fase:
        L.append("Fase: %s" % fase)
    L.append(free_float.catalyst_line(code, today=_today()))
    L.append("Status: %s" % KET.get(kind, kind))
    return "\n".join(L)


# ---------- deteksi sinyal dari candle (urut lama -> baru, terakhir = hari ini) ----------
def _ema(v, n):
    k = 2.0 / (n + 1); e = v[0]; out = [e]
    for x in v[1:]:
        e = x * k + e * (1 - k); out.append(e)
    return out


def _rsi(c, n=14):
    if len(c) <= n:
        return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]; g += max(d, 0); l += max(-d, 0)
    g /= n; l /= n
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]; g = (g * (n - 1) + max(d, 0)) / n; l = (l * (n - 1) + max(-d, 0)) / n
    return 100.0 if l == 0 else 100 - 100 / (1 + g / l)


def _tick(p):
    return 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25


ARA_RULE_EFFECTIVE = datetime.date(2026, 9, 28)
def _board_kind(board):
    """Normalisasi papan untuk tabel auto-rejection BEI yang berlaku."""
    s = str(board or "regular").strip().lower().replace("-", "_").replace(" ", "_")
    if any(x in s for x in ("akselerasi", "acceleration", "pemantauan", "monitoring", "fca", "special")):
        return "special"
    return "regular"  # Papan Utama, Pengembangan, dan Ekonomi Baru


def ara_price(prev, board="regular", as_of=None):
    """Batas atas teoritis dari acuan BEI, efektif 28 Sep 2026; bukan jaminan fill."""
    try:
        prev = float(prev)
        if prev <= 0:
            return None
        if as_of and datetime.date.fromisoformat(str(as_of)[:10]) < ARA_RULE_EFFECTIVE:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    if prev <= 10:
        raw = prev + 1
    elif _board_kind(board) == "special":
        raw = prev * 1.10
    else:
        pct = 0.35 if prev <= 200 else 0.25 if prev <= 5000 else 0.20
        raw = prev * (1 + pct)
    tick = _tick(raw)
    return math.floor(raw / tick + 1e-12) * tick


def _bid_offer_snapshot(metadata, day):
    """Rasio snapshot bid/offer hanya bila tanggal ringkasan sama dengan tanggal candle."""
    if not isinstance(metadata, dict) or str(metadata.get("bid_offer_date", ""))[:10] != str(day)[:10]:
        return None
    try:
        bid = float(metadata.get("bid_volume") or 0)
        offer = float(metadata.get("offer_volume") or 0)
    except (TypeError, ValueError):
        return None
    if bid <= 0 or offer <= 0:
        return None
    return {"bid_volume": bid, "offer_volume": offer, "ratio": bid / offer, "date": str(day)[:10]}


def _bb(vals, n=20):
    w = vals[-n:]; m = sum(w) / len(w); sd = (sum((x - m) ** 2 for x in w) / len(w)) ** 0.5
    return m, m - 2 * sd


def _rsi_series(values, n=14):
    """RSI Wilder per bar, untuk membandingkan RSI pada dua pivot low yang sudah terkonfirmasi."""
    out = [None] * len(values)
    if len(values) <= n:
        return out
    gain = loss = 0.0
    for i in range(1, n + 1):
        delta = values[i] - values[i - 1]
        gain += max(delta, 0.0); loss += max(-delta, 0.0)
    gain /= n; loss /= n
    out[n] = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
    for i in range(n + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = (gain * (n - 1) + max(delta, 0.0)) / n
        loss = (loss * (n - 1) + max(-delta, 0.0)) / n
        out[i] = 100.0 if loss == 0 else 100.0 - 100.0 / (1.0 + gain / loss)
    return out


def _amd_buy_context(cs):
    """AMD BUY proxy dari candle harian: Senin Q1, Selasa Q2, Rabu-Jumat Q3/X.
    Ini bukan bukti sesi intraday M1/M3/M5. Q1 range dinilai relatif ATR harian.
    """
    try:
        if len(cs) < 20:
            return {"valid": False, "phase_bullish": False}
        bars = [{"date": datetime.date.fromisoformat(str(x["date"])[:10]),
                 "o": float(x.get("open") or x.get("close")), "h": float(x["high"]),
                 "l": float(x["low"]), "c": float(x["close"])} for x in cs]
        last = bars[-1]
        week = lambda d: d.toordinal() - d.weekday()
        monday = tuesday = None; monday_i = tuesday_i = None
        for idx in range(len(bars) - 1, -1, -1):
            bar = bars[idx]
            if week(bar["date"]) != week(last["date"]):
                break
            if bar["date"].isoweekday() == 1:
                monday, monday_i = bar, idx
            elif bar["date"].isoweekday() == 2:
                tuesday, tuesday_i = bar, idx
        phase = _amdx(cs)
        phase_bullish = bool(phase and phase.endswith("↗") and
                             (phase.startswith("Distribution") or phase.startswith("X")))
        if not monday or not tuesday or last["date"].isoweekday() < 3:
            return {"valid": False, "phase_bullish": phase_bullish, "phase": phase}
        # ATR Wilder pada bar Q1 untuk menghindari Q1 yang terlalu lebar dianggap akumulasi.
        trs = []; atrs = []; prev = None
        for bar in bars[:monday_i + 1]:
            tr = bar["h"] - bar["l"] if prev is None else max(bar["h"] - bar["l"], abs(bar["h"] - prev), abs(bar["l"] - prev))
            trs.append(tr)
            if len(atrs) < 14:
                atrs.append(sum(trs) / len(trs))
            else:
                atrs.append((atrs[-1] * 13 + tr) / 14)
            prev = bar["c"]
        q1_atr = max(1.0, atrs[-1] if atrs else monday["h"] - monday["l"])
        q1_range = monday["h"] - monday["l"]
        q1_range_ok = 0.25 * q1_atr <= q1_range <= 2.2 * q1_atr
        swept = tuesday["l"] < monday["l"] and tuesday["c"] > monday["l"]
        reclaimed = (last["c"] > tuesday["h"] and last["c"] > tuesday["c"] and
                     monday["l"] <= last["c"] <= monday["h"])
        mss = last["c"] > tuesday["h"] and last["c"] > tuesday["c"]
        hi20 = max(b["h"] for b in bars[-21:-1])
        pullback_ok = hi20 > 0 and last["c"] <= REV_MAX_HI20 * hi20
        valid = bool(q1_range_ok and swept and reclaimed and mss and phase_bullish and pullback_ok)
        return {"valid": valid, "phase_bullish": phase_bullish, "phase": phase, "pullback_ok": pullback_ok,
                "hi20_ratio": (last["c"] / hi20) if hi20 > 0 else None,
                "q1_high": monday["h"], "q1_low": monday["l"], "q1_range": q1_range,
                "q1_range_ok": q1_range_ok, "q1_atr": q1_atr,
                "true_open": tuesday["o"], "sweep_low": tuesday["l"],
                "q2_high": tuesday["h"], "q2_open": tuesday["o"], "q2_close": tuesday["c"],
                "q1_mid": (monday["h"] + monday["l"]) / 2.0,
                "swept": swept, "reclaimed": reclaimed, "mss": mss}
    except (KeyError, TypeError, ValueError, OverflowError):
        return {"valid": False, "phase_bullish": False}


def _day_frac(date):
    n = live.now_wib()
    if date != n.date().isoformat():
        return 1.0
    return min(1.0, max(0.25, (n.hour * 60 + n.minute - 540) / 410.0))      # proyeksi volume harian dari bar yang masih berjalan


def _pre_takeoff_buy(code, candles, radar, cfg=None):
    """Paper BUY alert: yesterday's cross-sectional radar plus today's live breakout confirmation.

    Radar data is from the prior official daily snapshot; trigger data is a provisional
    Yahoo Finance daily bar during the current session. This is a heuristic, not a
    probability estimate or evidence of an executable fill.
    """
    cfg = cfg or DEFAULTS
    if not isinstance(radar, dict) or not radar.get("candidate") or len(candles) < 21:
        return None
    today = _today()
    day = str(candles[-1].get("date", ""))[:10]
    prior_day = str(candles[-2].get("date", ""))[:10]
    if day != today or str(radar.get("asof", ""))[:10] != prior_day:
        return None
    try:
        opens = [float(x["open"]) for x in candles]
        highs = [float(x["high"]) for x in candles]
        lows = [float(x["low"]) for x in candles]
        closes = [float(x["close"]) for x in candles]
        volumes = [float(x.get("volume", 0) or 0) for x in candles]
        price, prev_close = closes[-1], closes[-2]
        day_range = highs[-1] - lows[-1]
        prior = candles[-21:-1]
        avg_volume = sum(volumes[-21:-1]) / 20.0
        avg_value = sum(float(x["close"]) * float(x.get("volume", 0) or 0) for x in prior) / 20.0
        avg_range = sum(float(x["high"]) - float(x["low"]) for x in prior) / 20.0
        trigger = max(highs[-21:-1])
        stop = min(lows[-6:-1])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if min(price, prev_close, opens[-1], day_range, avg_volume, avg_value, avg_range, trigger, stop) <= 0:
        return None

    change_pct = (price / prev_close - 1.0) * 100.0
    close_position = (price - lows[-1]) / day_range
    range_expansion = day_range / avg_range
    fraction = _day_frac(day)
    relative_volume = (volumes[-1] / fraction) / avg_volume
    relative_value = ((price * volumes[-1]) / fraction) / avg_value
    min_rvol = float(cfg.get("top_gainer_min_rvol", 1.5))
    min_value_ratio = float(cfg.get("top_gainer_min_value_ratio", 1.5))
    min_range_expansion = float(cfg.get("top_gainer_min_range_expansion", 1.1))
    min_close_position = float(cfg.get("top_gainer_min_close_position", 0.6))
    max_chase = float(cfg.get("top_gainer_max_chase_pct", 8.0))
    min_avg_value = float(cfg.get("top_gainer_min_value", 250_000_000))

    if (price <= trigger or price <= opens[-1] or change_pct <= 0 or change_pct > max_chase
            or close_position < min_close_position or range_expansion < min_range_expansion
            or max(avg_value, 0.0) < min_avg_value
            or (relative_volume < min_rvol and relative_value < min_value_ratio)):
        return None
    risk = price - stop
    risk_pct = risk / price * 100.0 if risk > 0 else 0.0
    if not risk > 0 or not float(cfg["min_stop_pct"]) <= risk_pct <= float(cfg["max_stop_pct"]):
        return None

    both_activity = relative_volume >= min_rvol and relative_value >= min_value_ratio
    score = min(5.0, 4.0 + 0.5 * both_activity + 0.5 * (range_expansion >= 1.5))
    radar_rank = radar.get("rank")
    radar_universe = radar.get("universe")
    factors = ["radar sesi sebelumnya masuk 10%% teratas (%s/%s)" % (radar_rank, radar_universe),
               "harga menembus high 20 sesi %.0f" % trigger,
               "volume proyeksi %.2fx; turnover proyeksi %.2fx" % (relative_volume, relative_value),
               "rentang hari ini %.2fx rata-rata 20 sesi" % range_expansion,
               "harga di %.0f%% rentang harian; perubahan sesi %+0.1f%%" % (close_position * 100, change_pct)]
    return {"code": code, "kind": TOP_GAINER_BUY_KIND, "price": price, "stop": stop,
            "t1": price + 1.5 * risk, "t2": price + 3.0 * risk, "score": score,
            "date": day, "scan_time": live.now_wib().strftime("%H:%M WIB"),
            "trig": trigger, "ref": "high 20 sesi", "top_gainer_score": radar.get("score"),
            "top_gainer_candidate": True, "top_gainer_rank": radar_rank,
            "top_gainer_universe": radar_universe, "top_gainer_asof": prior_day,
            "top_gainer_reasons": radar.get("reasons") or [],
            "pre_takeoff_factors": factors,
            "pre_takeoff_relative_volume": relative_volume,
            "pre_takeoff_relative_value": relative_value,
            "pre_takeoff_range_expansion": range_expansion,
            "pre_takeoff_close_position": close_position,
            "pre_takeoff_return_pct": change_pct,
            "pre_takeoff_data_source": "Yahoo Finance OHLCV harian (dapat tertunda sekitar 10–15 menit), bar sesi berjalan provisional; radar dari Ringkasan Saham BEI",
            "pre_takeoff_signal": "Paper research alert; bukan probabilitas atau perintah order"}


def _atr_last(candles, n=14):
    if not candles:
        return 0.0
    trs = []
    prev = None
    for x in candles[-(n + 1):]:
        hi, lo, cl = float(x["high"]), float(x["low"]), float(x["close"])
        tr = hi - lo if prev is None else max(hi - lo, abs(hi - prev), abs(lo - prev))
        trs.append(tr); prev = cl
    return sum(trs[-n:]) / max(1, len(trs[-n:]))


def _foreign_flow_component(metadata):
    """Optional 5-point proxy; active only with at least three official flow days."""
    if not isinstance(metadata,dict): return None
    try:
        days=int(metadata.get("foreign_flow_coverage_days") or 0)
        ratio=float(metadata.get("foreign_flow_ratio_5d"))
    except (TypeError,ValueError,OverflowError): return None
    if days<3: return None
    points=5.0 if ratio>=.05 else 3.0 if ratio>=.02 else 1.5 if ratio>0 else 0.0
    return {"points":points,"ratio":ratio,"days":days,"asof":metadata.get("foreign_flow_asof")}


def _ara_breakout_candidate(code, candles, metadata=None, cfg=None):
    """Tahap 2: breakout resistance 10/20 sesi sudah terkonfirmasi, tetapi harga belum terlalu jauh dari batas ARA.
    Menghasilkan alert potensi/konfirmasi breakout, bukan klaim pasti menyentuh ARA.
    """
    cfg = cfg or DEFAULTS
    if len(candles) < 25:
        return None
    try:
        c = [float(x["close"]) for x in candles]; h = [float(x["high"]) for x in candles]
        lo = [float(x["low"]) for x in candles]; o = [float(x["open"]) for x in candles]
        v = [float(x.get("volume", 0) or 0) for x in candles]
        p, prev = c[-1], c[-2]
        if p <= 0 or prev <= 10:
            return None
        board = (metadata or {}).get("ara_board", cfg.get("ara_board", "regular"))
        ara = ara_price(prev, board=board, as_of=candles[-1].get("date"))
        if ara is None or ara <= p:
            return None
        cap_move = ara / prev - 1.0; day_move = p / prev - 1.0
        resistance = max(max(h[-11:-1]), max(h[-21:-1]))
        atr = max(1.0, _atr_last(candles[:-1], 14))
        extension = (p / resistance - 1.0) if resistance > 0 else 99
        max_extension = max(0.015, 0.45 * atr / p)
        frac = _day_frac(str(candles[-1].get("date", ""))[:10])
        vavg = sum(v[-21:-1]) / 20.0
        projected_volume = v[-1] / frac
        rvol = projected_volume / vavg if vavg > 0 else 0.0
        projected_value = p * projected_volume
        min_value = float(cfg.get("ara_min_value", 500_000_000))
        candle_range = h[-1] - lo[-1]
        close_pos = (p - lo[-1]) / candle_range if candle_range > 0 else 0.5
        green = p >= o[-1] and p >= prev
        # Hard gate: close berada di atas high 10/20 sesi, masih dalam 65% gerak ARA,
        # close kuat, volume dan nilai transaksi layak, serta tidak mengejar terlalu jauh.
        hard_gate = (p > resistance and 0 <= day_move <= 0.65 * cap_move
                     and 0 < extension <= max_extension and green and close_pos >= 0.70
                     and rvol >= 1.5 and projected_value >= min_value)
        if not hard_gate:
            return None
        ema20 = _ema(c, 20); above_ema = p >= ema20[-1] * 0.98; ema_rising = ema20[-1] >= ema20[-4]
        shares = 0.0
        if isinstance(metadata, dict):
            shares = float(metadata.get("tradeable_shares") or metadata.get("tradable_shares") or 0)
        float_turnover = projected_volume / shares if shares > 0 else None
        ranges = [max(0.0, h[i] - lo[i]) for i in range(len(c) - 21, len(c) - 1)]
        prior5 = sum(ranges[-5:]) / max(1, len(ranges[-5:]))
        prior15 = sum(ranges[:-5]) / max(1, len(ranges[:-5]))
        compression = prior5 / prior15 if prior15 > 0 else 1.0
        upv = sum(v[i] for i in range(-5, 0) if c[i] >= c[i-1])
        totalv = sum(v[-5:]); up_share = upv / totalv if totalv > 0 else 0.0
        score = 20.0  # close sudah menembus resistance 10/20 sesi
        reasons = ["close mengonfirmasi breakout di atas resistance %s" % rp(resistance)]
        if rvol >= 3: score += 18; reasons.append("relative volume %.2fx" % rvol)
        elif rvol >= 2: score += 15; reasons.append("relative volume %.2fx" % rvol)
        else: score += 10; reasons.append("relative volume %.2fx" % rvol)
        if close_pos >= .90: score += 15; reasons.append("close di 10%% teratas candle".replace("%%", "%"))
        elif close_pos >= .80: score += 12; reasons.append("close kuat di atas 80% rentang candle")
        else: score += 9; reasons.append("close di atas 70% rentang candle")
        if compression <= .85: score += 8; reasons.append("volatility contraction sebelum breakout")
        if above_ema: score += 6; reasons.append("harga di atas EMA20")
        if ema_rising: score += 4; reasons.append("EMA20 menanjak")
        if projected_value >= 2_000_000_000: score += 10; reasons.append("nilai transaksi proyeksi ≥ Rp2 miliar")
        elif projected_value >= min_value: score += 7; reasons.append("nilai transaksi proyeksi memenuhi ambang")
        if float_turnover is not None:
            if float_turnover >= .01: score += 8; reasons.append("turnover saham tradable ≥1%" )
            elif float_turnover >= .003: score += 6; reasons.append("turnover saham tradable ≥0,3%")
            elif float_turnover >= .001: score += 3; reasons.append("turnover saham tradable ≥0,1%")
        if up_share >= .65: score += 5; reasons.append("volume candle naik dominan 5 sesi")
        elif up_share >= .55: score += 3; reasons.append("volume candle naik mulai dominan")
        bid_offer = _bid_offer_snapshot(metadata, str(candles[-1].get("date", ""))[:10])
        if bid_offer and bid_offer["ratio"] >= 2.0:
            score += 5; reasons.append("snapshot bid/offer %.2fx pada %s (konfirmasi heuristik)" %
                                       (bid_offer["ratio"], bid_offer["date"]))
        flow_component=_foreign_flow_component(metadata)
        if flow_component:
            score+=flow_component["points"]
            reasons.append("arus asing net 5 sesi %+0.1f%% nilai transaksi (proxy): +%.1f/5 poin" %
                           (flow_component["ratio"]*100,flow_component["points"]))
        else: reasons.append("data arus asing resmi <3 sesi; komponen dikeluarkan dari skor")
        if day_move <= .25 * cap_move: score += 6; reasons.append("kenaikan harian masih tahap awal terhadap batas ARA")
        elif day_move <= .45 * cap_move: score += 3; reasons.append("kenaikan belum terlalu jauh dari batas ARA")
        score_max=100.0+(5.0 if bid_offer else 0.0)+(5.0 if flow_component else 0.0)
        score100=min(100.0,score*100.0/score_max)
        if score100 < float(cfg.get("ara_breakout_min_score100", 65)):
            return None
        support = min(lo[-6:-1]); stop = support - .12 * atr
        risk = p - stop
        if risk <= 0 or risk / p > .08 or risk / p < .0075:
            return None
        t1 = p + 1.2 * risk; t2 = ara
        if not (stop < p < t1 < t2):
            return None
        return {"code": code, "kind": "ara_breakout", "price": p, "stop": stop, "t1": t1, "t2": t2,
                "trig": resistance, "ref": "high 10/20 sesi terkonfirmasi", "score": score100 / 20.0,
                "ara_score": round(score100, 1), "ara_stage": "BREAKOUT TERKONFIRMASI",
                "ara_price": ara, "ara_rule_effective": ARA_RULE_EFFECTIVE.isoformat(),
                "ara_board": _board_kind(board), "ara_board_assumed": not bool((metadata or {}).get("ara_board")),
                "bid_offer_snapshot": bid_offer,
                "resistance": resistance, "relative_volume": round(rvol, 2),
                "projected_value": round(projected_value),
                "turnover_float": None if float_turnover is None else round(float_turnover * 100, 3),
                "foreign_flow_ratio_5d": flow_component["ratio"] if flow_component else None,
                "foreign_flow_coverage_days": flow_component["days"] if flow_component else int((metadata or {}).get("foreign_flow_coverage_days") or 0),
                "foreign_flow_asof": flow_component["asof"] if flow_component else (metadata or {}).get("foreign_flow_asof"),
                "ara_reasons": reasons, "date": str(candles[-1].get("date", ""))[:10],
                "low": lo[-1], "high": h[-1], "fase": _amdx(candles)}
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return None


def _early_ara_candidate(code, candles, metadata=None, cfg=None):
    """Kandidat pra-ARA (belum breakout) dari kompresi, relative volume, kekuatan close,
    kedekatan resistance, trend, value dan turnover terhadap saham tradable bila tersedia.
    Memakai candle harian berjalan dari yfinance; bukan order-book realtime dan bukan prediksi pasti.
    """
    cfg = cfg or DEFAULTS
    if len(candles) < 25:
        return None
    try:
        c = [float(x["close"]) for x in candles]
        h = [float(x["high"]) for x in candles]
        lows = [float(x["low"]) for x in candles]
        opens = [float(x["open"]) for x in candles]
        vols = [float(x.get("volume", 0) or 0) for x in candles]
        day = str(candles[-1].get("date", ""))[:10]
        p, prev = c[-1], c[-2]
        if p <= 0 or prev <= 10:
            return None
        board = (metadata or {}).get("ara_board", cfg.get("ara_board", "regular"))
        ara = ara_price(prev, board=board, as_of=day)
        if ara is None or ara <= p:
            return None
        cap_move = ara / prev - 1.0
        day_move = p / prev - 1.0
        frac = _day_frac(day)
        vavg = sum(vols[-21:-1]) / 20.0
        projected_volume = vols[-1] / frac
        rvol = projected_volume / vavg if vavg > 0 else 0.0
        projected_value = p * projected_volume
        min_value = float(cfg.get("ara_min_value", 500_000_000))
        atr = max(1.0, _atr_last(candles[:-1], 14))
        rg = h[-1] - lows[-1]
        close_pos = (p - lows[-1]) / rg if rg > 0 else 0.5
        green = p >= opens[-1] and p >= prev
        # Resistance yang belum ditembus: pilih level 10/20 hari terdekat di atas harga.
        candidates = [max(h[-11:-1]), max(h[-21:-1])]
        above = [x for x in candidates if x > p]
        if not above:
            # Setelah resistance pecah, kandidat masuk tahap breakout terkonfirmasi.
            return _ara_breakout_candidate(code, candles, metadata=metadata, cfg=cfg)
        resistance = min(above)
        distance = (resistance - p) / p
        max_distance = max(0.015, 0.55 * atr / p)
        near_resistance = 0 < distance <= max_distance and resistance < ara
        # Kompresi sebelum sesi saat ini; current candle tidak ikut agar tidak look-ahead.
        ranges = [max(0.0, h[i] - lows[i]) for i in range(len(c) - 21, len(c) - 1)]
        prior5 = sum(ranges[-5:]) / max(1, len(ranges[-5:]))
        prior15 = sum(ranges[:-5]) / max(1, len(ranges[:-5]))
        compression_ratio = prior5 / prior15 if prior15 > 0 else 1.0
        compressed = compression_ratio <= 0.95
        ema20 = _ema(c, 20)
        above_ema = p >= ema20[-1] * 0.98
        ema_rising = ema20[-1] >= ema20[-4]
        rsi_now = _rsi(c)
        rsi_prev = _rsi(c[:-1])
        rsi_turn = rsi_now is not None and rsi_prev is not None and 48 <= rsi_now <= 72 and rsi_now >= rsi_prev
        # Akumulasi ringan 5 sesi: porsi volume yang terjadi pada candle naik.
        ups = 0.0; total5 = 0.0
        for i in range(-5, 0):
            total5 += vols[i]
            if c[i] >= c[i - 1]:
                ups += vols[i]
        up_volume_share = ups / total5 if total5 > 0 else 0.0
        shares = 0.0
        if isinstance(metadata, dict):
            shares = float(metadata.get("tradeable_shares") or metadata.get("tradable_shares") or 0)
        float_turnover = projected_volume / shares if shares > 0 else None
        # Skor awal 0-100. Turnover free-float dinamis: bobotnya tidak dihitung bila datanya tidak tersedia.
        bid_offer = _bid_offer_snapshot(metadata, day)
        flow_component=_foreign_flow_component(metadata)
        score=0.0
        max_score=(90.0 if float_turnover is None else 100.0)+(5.0 if bid_offer else 0.0)+(5.0 if flow_component else 0.0)
        reasons=[]
        if bid_offer and bid_offer["ratio"] >= 2.0:
            score+=5.0
            reasons.append("snapshot bid/offer %.2fx pada %s (konfirmasi heuristik, bukan orderbook intraday)" %
                           (bid_offer["ratio"],bid_offer["date"]))
        if flow_component:
            score+=flow_component["points"]
            reasons.append("arus asing net 5 sesi %+0.1f%% nilai transaksi (proxy): +%.1f/5 poin" %
                           (flow_component["ratio"]*100,flow_component["points"]))
        else: reasons.append("data arus asing resmi <3 sesi; komponen dikeluarkan dari skor")
        if near_resistance:
            score += 15; reasons.append("harga tinggal %.2f%% dari resistance %s" % (distance * 100, rp(resistance)))
        if rvol >= 3.0:
            score += 20; reasons.append("relative volume %.2fx" % rvol)
        elif rvol >= 2.5:
            score += 18; reasons.append("relative volume %.2fx" % rvol)
        elif rvol >= 2.0:
            score += 16; reasons.append("relative volume %.2fx" % rvol)
        elif rvol >= 1.5:
            score += 12; reasons.append("relative volume %.2fx" % rvol)
        if close_pos >= 0.90:
            score += 15; reasons.append("close di 10% teratas rentang candle")
        elif close_pos >= 0.80:
            score += 12; reasons.append("close kuat di atas 80%% rentang candle")
        elif close_pos >= 0.70:
            score += 9; reasons.append("close di atas 70%% rentang candle")
        elif close_pos >= 0.65:
            score += 6; reasons.append("close di atas 65%% rentang candle")
        if compression_ratio <= 0.85:
            score += 10; reasons.append("volatility contraction 5/15 sesi %.2f" % compression_ratio)
        elif compression_ratio <= 0.95:
            score += 7; reasons.append("range 5 sesi mulai menyempit")
        if above_ema:
            score += 7; reasons.append("harga bertahan di sekitar/atas EMA20")
        if ema_rising:
            score += 3; reasons.append("EMA20 mulai menanjak")
        if projected_value >= 2_000_000_000:
            score += 10; reasons.append("nilai transaksi proyeksi ≥ Rp2 miliar")
        elif projected_value >= 1_000_000_000:
            score += 8; reasons.append("nilai transaksi proyeksi ≥ Rp1 miliar")
        elif projected_value >= min_value:
            score += 6; reasons.append("likuiditas melewati ambang nilai transaksi")
        if float_turnover is not None:
            if float_turnover >= 0.01:
                score += 10; reasons.append("turnover saham tradable ≥1%")
            elif float_turnover >= 0.003:
                score += 8; reasons.append("turnover saham tradable ≥0,3%")
            elif float_turnover >= 0.001:
                score += 5; reasons.append("turnover saham tradable ≥0,1%")
        if up_volume_share >= 0.65:
            score += 5; reasons.append("volume lebih dominan pada candle naik 5 sesi")
        elif up_volume_share >= 0.55:
            score += 3; reasons.append("akumulasi volume 5 sesi mulai positif")
        if 0 <= day_move <= 0.25 * cap_move:
            score += 5; reasons.append("kenaikan harian masih tahap awal terhadap batas ARA")
        elif day_move <= 0.40 * cap_move:
            score += 3; reasons.append("kenaikan belum terlalu jauh dari harga sebelumnya")
        score100 = min(100.0, score * 100.0 / max_score)
        hard_gate = (near_resistance and green and close_pos >= 0.65 and rvol >= 1.5
                     and projected_value >= min_value and 0 <= day_move <= 0.45 * cap_move)
        min_score = float(cfg.get("ara_early_min_score100", 62))
        if not hard_gate or score100 < min_score:
            return None
        # Stop di bawah support 5 sesi; risk dibatasi agar kandidat tidak mendorong mengejar saham terlalu jauh.
        support = min(lows[-6:-1])
        stop = support - 0.12 * atr
        risk = p - stop
        if risk <= 0 or risk / p > 0.08 or risk / p < 0.0075:
            return None
        trigger = resistance
        t1 = max(trigger, p + 1.2 * risk)
        t2 = ara
        if not (stop < p < t1 < t2):
            return None
        return {"code": code, "kind": "ara_early", "price": p, "stop": stop,
                "t1": t1, "t2": t2, "trig": trigger, "ref": "resistance 10/20 hari",
                "score": score100 / 20.0, "ara_score": round(score100, 1),
                "ara_stage": "PRE-BREAKOUT", "ara_price": ara,
                "ara_rule_effective": ARA_RULE_EFFECTIVE.isoformat(), "ara_board": _board_kind(board),
                "ara_board_assumed": not bool((metadata or {}).get("ara_board")),
                "bid_offer_snapshot": bid_offer, "resistance": resistance,
                "relative_volume": round(rvol, 2), "projected_value": round(projected_value),
                "turnover_float": None if float_turnover is None else round(float_turnover * 100, 3),
                "foreign_flow_ratio_5d": flow_component["ratio"] if flow_component else None,
                "foreign_flow_coverage_days": flow_component["days"] if flow_component else int((metadata or {}).get("foreign_flow_coverage_days") or 0),
                "foreign_flow_asof": flow_component["asof"] if flow_component else (metadata or {}).get("foreign_flow_asof"),
                "ara_reasons": reasons, "date": day, "low": lows[-1], "high": h[-1],
                "fase": _amdx(candles)}
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return None


def _scan_raw(code, candles, metadata=None, cfg=None):
    """candles: list dict {date,open,high,low,close,volume}. -> list item sinyal beli dan setup reversal. Tiap item dapat membawa status OTE, konteks AMD, dan stage deteksi ARA."""
    cfg = cfg or DEFAULTS
    if len(candles) < 25:
        return []
    c = [float(x["close"]) for x in candles]; h = [float(x["high"]) for x in candles]
    lo = [float(x["low"]) for x in candles]; o = [float(x["open"]) for x in candles]
    d = str(candles[-1].get("date", ""))[:10]; p = c[-1]
    stop = min(lo[-5:]); stop = stop if stop < p else p * 0.95
    risk = p - stop
    amd = _amd_buy_context(candles)
    phase_text = amd.get("phase") or _amdx(candles)
    base = {"code": code, "price": p, "stop": stop, "t1": p + 1.5 * risk, "t2": p + 3 * risk,
            "date": d, "fase": phase_text}
    out = []; ote_tag = None
    early_ara = _early_ara_candidate(code, candles, metadata=metadata, cfg=cfg)
    if early_ara:
        out.append(early_ara)
    rsi_series = _rsi_series(c)
    # ---------- REVERSAL BUY: AMD Q1/Q2 -> Q3/X bullish MSS + FVG/OB ----------
    # Syarat keras: Q2 menyapu low Q1 lalu reclaim; Q3/X bullish phase; close menembus high Q2;
    # zona FVG/OB untuk limit entry harus berada di discount (di bawah True Open dan midpoint Q1).
    if amd.get("valid"):
        q2_low = float(amd["sweep_low"]); true_open = float(amd["true_open"])
        discount_ceiling = min(true_open, float(amd["q1_mid"]))
        q1_high, q1_low = float(amd["q1_high"]), float(amd["q1_low"])
        q1_range = max(1.0, q1_high - q1_low)
        zone = None; source = None
        # Bullish FVG 3-bar (daily proxy), harus berada di discount.
        atr_now = max(1.0, _atr_last(candles))
        if lo[-1] > h[-3] and lo[-1] - h[-3] >= 0.08 * atr_now:
            zlo, zhi = h[-3], lo[-1]
            if zlo < zhi and (zlo + zhi) / 2.0 < discount_ceiling:
                zone, source = (zlo, min(zhi, discount_ceiling)), "Bullish FVG (proxy harian)"
        # OB: candle bearish Q2 yang membentuk sweep. Pakai body/range bawah dan batasi ke discount.
        if zone is None:
            q2_open = float(amd.get("q2_open", true_open)); q2_close = float(amd.get("q2_close", q2_low))
            if q2_close < q2_open:
                zlo = q2_low
                zhi = min(q2_open, discount_ceiling)
                if zlo < zhi:
                    zone, source = (zlo, zhi), "Bullish OB Q2 (proxy harian)"
            elif q2_low < discount_ceiling:
                # Fallback diberi label proxy agar tidak mengklaim OB intraday yang tidak tersedia.
                zlo, zhi = q2_low, discount_ceiling
                if zlo < zhi:
                    zone, source = (zlo, zhi), "Sweep-base demand (proxy harian)"
        mss = p > float(amd.get("q2_high", 0)) and p > c[-2] and p > o[-1]
        rg = h[-1] - lo[-1]
        close_pos = (p - lo[-1]) / rg if rg > 0 else 0.5
        displacement = (p - o[-1]) >= 0.45 * atr_now and close_pos >= 0.68
        div = False
        pivots = [i for i in range(max(15, len(c) - 24), len(c) - 2)
                  if lo[i] <= lo[i - 1] and lo[i] <= lo[i + 1] and rsi_series[i] is not None]
        if len(pivots) >= 2:
            i1, i2 = pivots[-2], pivots[-1]
            div = lo[i2] < lo[i1] - 0.15 * atr_now and rsi_series[i2] >= rsi_series[i1] + 3.0
        r_prev = _rsi(c[:-1]); r_now = _rsi(c)
        rsi_hook = r_prev is not None and r_now is not None and r_now > r_prev and r_prev <= 45
        volumes = [float(x.get("volume", 0) or 0) for x in candles[-21:-1]]
        vavg_rev = sum(volumes) / max(1, len(volumes))
        vratio = (float(candles[-1].get("volume", 0) or 0) / _day_frac(d) / vavg_rev) if vavg_rev > 0 else 0.0
        if zone and mss and displacement:
            entry_lo, entry_hi = map(float, zone)
            entry = (entry_lo + entry_hi) / 2.0
            sl = min(q2_low, entry_lo) - 0.20 * atr_now
            risk = entry - sl
            # OTE 62%-79% pada swing naik terakhir; konfluensi tambahan, bukan hard gate.
            ote_overlap = False
            hseg = h[-30:]; hmax = max(hseg); ih = len(hseg) - 1 - hseg[::-1].index(hmax)
            if ih > 2:
                lmin = min(lo[-30:][:ih]); swing = hmax - lmin
                if swing > 0:
                    ote_lo, ote_hi = hmax - 0.79 * swing, hmax - 0.62 * swing
                    ote_overlap = max(entry_lo, ote_lo) <= min(entry_hi, ote_hi)
            # TP1 ke high Q1; TP2 ke ekstensi 2.5x range Q1 (fallback 2.5R jika tidak berurutan).
            far = q1_high if q1_high > entry + 1.2 * risk else entry + 1.5 * risk       # target struktur lama -> kini TP2
            target1 = entry + REV_TP1_R * risk                                         # TP1 dekat -> winrate lebih tinggi
            target2 = far
            target_ok = target1 > entry and target2 > target1
            # Model B: AMD BUY Quality Score (100). Hard gate AMD tetap wajib;
            # skor meranking kualitas struktur, pressure, momentum, pullback, dan risk.
            q1_part = 5 if amd.get("q1_range_ok") else 0
            sweep_atr = max(0.0, (q1_low - q2_low) / atr_now)
            sweep_part = 6 if sweep_atr >= 0.20 else 4 if sweep_atr >= 0.05 else 2
            reclaim_part = 6 if amd.get("reclaimed") else 0
            mss_part = 8 if p - float(amd.get("q2_high", 0)) >= 0.10 * atr_now else 6
            structure_score = q1_part + sweep_part + reclaim_part + mss_part

            pressure_candle = 5 if p > o[-1] else 0
            pressure_close = 7 if close_pos >= 0.80 else 5 if close_pos >= 0.70 else 3 if close_pos >= 0.60 else 0
            pressure_displacement = 6 if (p - o[-1]) >= 0.75 * atr_now else 4 if displacement else 0
            pressure_volume = 7 if vratio >= 2.0 else 5 if vratio >= 1.5 else 3 if vratio >= 1.2 else 0
            pressure_score = pressure_candle + pressure_close + pressure_displacement + pressure_volume

            trend_phase = 8 if amd.get("phase_bullish") else 0
            trend_rsi = 4 if r_now is not None and 50 <= r_now <= 70 else 2 if r_now is not None and 45 <= r_now <= 75 else 0
            trend_hook = 4 if rsi_hook else 0
            trend_div = 4 if div else 0
            trend_score = trend_phase + trend_rsi + trend_hook + trend_div

            hi20_ratio = float(amd.get("hi20_ratio") or 1.0)
            pullback_depth = 9 if hi20_ratio <= 0.80 else 7 if hi20_ratio <= 0.84 else 5 if hi20_ratio <= REV_MAX_HI20 else 0
            entry_mid = (entry_lo + entry_hi) / 2.0
            pullback_discount = 6 if entry_hi <= discount_ceiling and entry_mid <= discount_ceiling - 0.10 * atr_now else 4 if entry_hi <= discount_ceiling else 0
            pullback_score = pullback_depth + pullback_discount

            avg_turnover = sum(float(x.get("close", 0) or 0) * float(x.get("volume", 0) or 0)
                               for x in candles[-21:-1]) / max(1, len(candles[-21:-1]))
            min_turnover = float((cfg or DEFAULTS).get("min_value", DEFAULTS["min_value"]))
            ara_turnover = float((cfg or DEFAULTS).get("ara_min_value", DEFAULTS["ara_min_value"]))
            liquidity_part = 7 if avg_turnover >= min_turnover else 5 if avg_turnover >= ara_turnover else 2 if avg_turnover > 0 else 0
            risk_pct = risk / max(entry, 1.0) * 100.0
            risk_part = 4 if 2.0 <= risk_pct <= 5.0 else 3 if 1.0 <= risk_pct <= 7.0 else 0
            rr2 = (target2 - entry) / risk if risk > 0 else 0
            rr_part = 4 if rr2 >= 2.5 else 3 if rr2 >= 1.5 else 0
            liquidity_risk_score = liquidity_part + risk_part + rr_part

            score100 = min(100.0, float(structure_score + pressure_score + trend_score + pullback_score + liquidity_risk_score))
            reasons = ["konteks pullback: close %.1f%% dari high 20 hari" % (100 * hi20_ratio),
                       "AMD Q1 range, Q2 sweep/reclaim dan Q3/X MSS tervalidasi", source]
            if pressure_volume:
                reasons.append("volume relatif %.1fx" % vratio)
            if pressure_displacement:
                reasons.append("bullish displacement dengan close position %.0f%%" % (close_pos * 100))
            if trend_div:
                reasons.append("bullish RSI divergence")
            elif trend_hook:
                reasons.append("RSI bullish hook")
            if ote_overlap:
                reasons.append("OTE 62%-79% overlap zona FVG/OB")
            if avg_turnover:
                reasons.append("rata-rata value 20 sesi Rp%.0f" % avg_turnover)
            reasons.append("risk %.2f%% · reward/risk TP2 %.2fR" % (risk_pct, rr2))
            amd_score_detail = {
                "structure": {"score": structure_score, "max": 25, "Q1_range": q1_part, "Q2_sweep": sweep_part,
                              "reclaim": reclaim_part, "MSS": mss_part},
                "buying_pressure": {"score": pressure_score, "max": 25, "bullish_candle": pressure_candle,
                                    "close_position": pressure_close, "displacement": pressure_displacement,
                                    "relative_volume": pressure_volume},
                "trend_momentum": {"score": trend_score, "max": 20, "phase": trend_phase,
                                   "RSI_zone": trend_rsi, "RSI_hook": trend_hook, "divergence": trend_div},
                "pullback_quality": {"score": pullback_score, "max": 15, "depth": pullback_depth,
                                     "discount": pullback_discount},
                "liquidity_risk": {"score": liquidity_risk_score, "max": 15, "liquidity": liquidity_part,
                                   "risk": risk_part, "reward_risk": rr_part},
                "total": round(score100, 1), "max": 100,
            }
            if risk > 0 and target_ok:
                out.append(dict(base, kind="reversal", price=entry, stop=sl, t1=target1, t2=target2,
                                score=score100 / 20.0, reversal_score=round(score100, 1), amd_quality_score=round(score100, 1),
                                entry_lo=entry_lo, entry_hi=entry_hi, entry_source=source,
                                true_open=true_open, q1_high=q1_high, q1_low=q1_low, sweep_low=q2_low,
                                amd_reasons=reasons, amd_context="Q1 Accumulation → Q2 Manipulation → Q3/X bullish confirmation",
                                date=d, phase=amd.get("phase"), ax=True, amd_phase_bullish=True,
                                ote="baru" if ote_overlap else None, low=lo[-1], high=h[-1], vratio=round(vratio, 2),
                                amd_score_detail=amd_score_detail))
    # ---------- OTE: retracement 62-79% dari swing 30 bar ----------
    seg = h[-30:]; H = max(seg); iH = len(seg) - 1 - seg[::-1].index(H)
    if iH > 2:
        L = min(lo[-30:][:iH]); rgs = H - L
        if rgs > 0:
            zhi, zlo = H - 0.62 * rgs, H - 0.79 * rgs
            in_zone = lo[-1] <= zhi and h[-1] >= zlo
            after = range(len(h) - 30 + iH + 1, len(h) - 1)
            touched = [i for i in after if lo[i] <= zhi and h[i] >= zlo]
            if in_zone and p > L:                                                  # 1) MENYENTUH zona hari ini
                ote_tag = "sentuh"
                out.append(dict(base, kind="ote", ote="sentuh", lo=zlo, hi=zhi, stop=L, t1=H, t2=H + 0.272 * rgs, low=lo[-1], high=h[-1]))
            if touched and p > zhi and c[-1] > c[-2] and min(lo[touched[0]:]) >= L:   # 2) BARU SAJA OTE: pernah sentuh, swing low utuh, kini keluar zona ke atas
                sl = min(lo[touched[0]:])
                t1, t2 = (H, H + 0.272 * rgs) if p < H * 0.995 else (H + 0.272 * rgs, H + 0.618 * rgs)
                if sl < p < t1 < t2:
                    ote_tag = ote_tag or "baru"
                    out.append(dict(base, kind="ote_bounce", ote="baru", stop=sl, t1=t1, t2=t2))
    if p > max(h[-21:-1]):
        out.append(dict(base, kind="breakout"))
    if lo[-2] < lo[-3] and c[-1] > h[-2]:
        out.append(dict(base, kind="mss"))
    e20, e50 = _ema(c, 20), _ema(c, 50); r = _rsi(c)
    if r is not None and p > e20[-1] > e50[-1] and e20[-1] > e20[-3] and 55 <= r <= 80:
        out.append(dict(base, kind="momentum"))
    rg = h[-1] - lo[-1]
    if c[-1] > o[-1] and c[-1] > c[-2] and rg > 0 and (c[-1] - o[-1]) / rg >= 0.6:
        out.append(dict(base, kind="bullish"))
    v = [float(x.get("volume", 0) or 0) for x in candles]; vavg = sum(v[-21:-1]) / 20.0
    vol_ok = vavg == 0 or v[-1] >= 1.3 * vavg
    r10h, r10l = max(h[-11:-1]), min(lo[-11:-1]); tight = (r10h - r10l) / p <= 0.08
    # ---------- TREND FOLLOWING ----------
    if e20[-1] > e50[-1] and e50[-1] > e50[-5] and p > e50[-1] and lo[-1] <= e20[-1] * 1.005 and c[-1] > e20[-1] and c[-1] > o[-1]:
        out.append(dict(base, kind="trend_pullback"))
    if any(e20[i - 1] <= e50[i - 1] and e20[i] > e50[i] for i in (-1, -2, -3)) and p > e20[-1]:
        out.append(dict(base, kind="trend_cross"))
    if tight and p > r10h and vol_ok:
        out.append(dict(base, kind="breakout_range"))
    # ---------- MEAN REVERSION (BUY; bukan trend-following EMA, tetapi tetap wajib bias AMD bullish) ----------
    sma, lbb = _bb(c); _, lbb_prev = _bb(c[:-1])
    rgm = h[-1] - lo[-1]; wick = (min(o[-1], c[-1]) - lo[-1]) / rgm if rgm > 0 else 0.0; posm = (p - lo[-1]) / rgm if rgm > 0 else 0.5
    green = c[-1] > o[-1] and c[-1] > c[-2]; dd = 1 - p / max(h[-11:-1])
    vxm = (v[-1] / _day_frac(d)) / vavg if vavg > 0 else 0
    amd_phase_bullish = bool(amd.get("phase_bullish"))
    if sma > p * 1.03 and green and amd_phase_bullish:                    # mean reversion hanya pada D/X yang mengarah naik
        ms = min(lo[-1], lo[-2]) * 0.995
        mb = dict(base, stop=ms, t1=p + 0.5 * (sma - p), t2=sma)
        msc = sum([vxm >= 1.5, r is not None and r <= 30, lo[-1] < lbb or c[-2] < lbb_prev, wick >= 0.4, dd >= 0.10])
        if dd >= 0.15 and vxm >= 2 and wick >= 0.4 and posm >= 0.6:
            out.append(dict(mb, kind="mr_capitulation", score=msc))
        if c[-2] < lbb_prev and p > lbb:
            out.append(dict(mb, kind="mr_bb_reclaim", score=msc))
        if r is not None and r <= 35 and posm >= 0.5:
            out.append(dict(mb, kind="mr_oversold", score=msc))
    # ---------- POTENSI BREAKOUT / POTENSI MSS (mendekati trigger, belum tembus) ----------
    pd_ = float(POT_DIST_PCT[0]) / 100.0
    def _pot(kind, trig, ref, st):
        rk = trig - st
        if rk > 0 and st < p <= trig:
            out.append(dict(base, kind=kind, stop=st, t1=trig + 1.5 * rk, t2=trig + 3 * rk, trig=trig, ref=ref))
    hh = max(h[-21:-1])
    if p > e20[-1] and p <= hh and hh / p - 1 <= pd_:
        _pot("potensi_breakout", hh, "high 20 hari", stop)
    elif tight and p > e20[-1] and p <= r10h and r10h / p - 1 <= pd_:
        _pot("potensi_breakout", r10h, "batas atas range 10 hari", stop)
    if lo[-2] < lo[-3] and c[-1] > o[-1] and p <= h[-2] and h[-2] / p - 1 <= pd_:
        _pot("potensi_mss", h[-2], "high kemarin", min(lo[-1], lo[-2]) * 0.995)
    # ---------- CALON ARA (murni dari data harga & volume) ----------
    pc = c[-2]
    board = (metadata or {}).get("ara_board", cfg.get("ara_board", "regular"))
    ara = ara_price(pc, board=board, as_of=d)
    if ara is not None:
        pct = ara / pc - 1.0
        chg = p / pc - 1; rgd = h[-1] - lo[-1]; posd = (p - lo[-1]) / rgd if rgd > 0 else 1.0
        vx = (v[-1] / _day_frac(d)) / vavg if vavg > 0 else 0
        if chg >= 0.4 * pct and posd >= 0.9 and vx >= 2:
            sc = sum([chg >= 0.6 * pct, posd >= 0.95, vx >= 3, p > max(h[-21:-1]), e20[-1] > e50[-1]])
            bo = _bid_offer_snapshot(metadata, d)
            if bo and bo["ratio"] >= 2.0:
                sc = min(5, sc + 1)
            ara_meta = {"ara_rule_effective": ARA_RULE_EFFECTIVE.isoformat(),
                        "ara_board": _board_kind(board),
                        "ara_board_assumed": not bool((metadata or {}).get("ara_board")),
                        "bid_offer_snapshot": bo,
                        "ara_reasons": (["snapshot bid/offer %.2fx pada %s (konfirmasi heuristik)" %
                                         (bo["ratio"], bo["date"])] if bo and bo["ratio"] >= 2.0 else [])}
            st = min(max(lo[-1], p * 0.92), p * 0.97)
            if p >= ara * 0.995:
                n1 = ara_price(p, board=board, as_of=d)
                out.append(dict(base, **ara_meta, kind="ara_lanjut", stop=st, t1=n1, t2=ara_price(n1, board=board, as_of=d), score=sc,
                                ara_stage="ARA TERSENTUH", ara_price=ara, ara_score=sc * 20))
            else:
                out.append(dict(base, **ara_meta, kind="ara_potensi", stop=st, t1=ara, t2=ara_price(ara, board=board, as_of=d), score=sc,
                                ara_stage="AKSELERASI MENUJU ARA", ara_price=ara, ara_score=sc * 20))
    for it in out:
        it.setdefault("ote", ote_tag)                                      # status OTE ikut di semua sinyal (pesan menampilkannya)
    return out


def _quality(it, cs, cfg):
    """Filter kualitas: syarat WAJIB (risk/reward, jarak stop, tidak mengejar, bukan saham receh) + skor konfirmasi 0-5."""
    c = [float(x["close"]) for x in cs]; h = [float(x["high"]) for x in cs]
    lo = [float(x["low"]) for x in cs]; v = [float(x["volume"] or 0) for x in cs]; o = [float(x["open"]) for x in cs]
    p = it["price"]
    if p < cfg["min_price"] or abs(p / c[-2] - 1) >= 0.2:
        return None
    risk = p - it["stop"]
    if risk <= 0 or not cfg["min_stop_pct"] <= risk / p * 100 <= cfg["max_stop_pct"]:
        return None
    if (it["t1"] - p) / risk + 1e-9 < cfg["min_rr"]:
        return None
    e20 = _ema(c, 20)[-1]; e50l = _ema(c, 50); e50 = e50l[-1]; r = _rsi(c); ch = cfg["max_chase_pct"] / 100.0
    if p > e20 * (1 + ch) or (r and r > 85):
        return None
    vavg = sum(v[-21:-1]) / 20.0; vproj = v[-1] / _day_frac(str(cs[-1].get("date", ""))[:10])
    rg = h[-1] - lo[-1]; pos = (p - lo[-1]) / rg if rg > 0 else 0.5
    conds = ([p > e50, e50 > e50l[-5], vproj >= vavg, pos >= 0.6, r is not None and 50 <= r <= 75] if cfg.get("trend_filter")
             else [vproj >= vavg, pos >= 0.6, c[-1] > o[-1], c[-1] > c[-2], r is not None and r <= 75])
    sc = sum(1 for x in conds if x)
    return sc if sc >= cfg["min_score"] else None


def scan(code, candles, cfg=None, metadata=None):
    cfg = cfg or DEFAULTS
    POT_DIST_PCT[0] = cfg.get("pot_dist_pct", 2.0)
    out = []
    raw_items = _scan_raw(code, candles, metadata=metadata, cfg=cfg)
    raw_kinds = {it.get("kind") for it in raw_items}
    for it in raw_items:
        kind = it["kind"]
        if kind not in cfg["kinds"]:
            continue
        if kind == "reversal":
            risk = it["price"] - it["stop"]
            if (it.get("score", 0) >= float(cfg.get("reversal_min_score", 4.0)) and risk > 0
                    and cfg["min_stop_pct"] <= risk / it["price"] * 100 <= cfg["max_stop_pct"]
                    and (it["t1"] - it["price"]) / risk + 1e-9 >= 1.2):
                out.append(it)
            continue
        if kind.startswith("mr_"):                                         # mean reversion tidak wajib OTE; bias AMD bullish sudah menjadi gate di _scan_raw
            risk = it["price"] - it["stop"]
            if (it.get("score", 0) >= cfg["mr_min_score"] and risk > 0 and it["price"] >= cfg["min_price"]
                    and cfg["min_stop_pct"] <= risk / it["price"] * 100 <= cfg["max_stop_pct"]
                    and (it["t2"] - it["price"]) / risk + 1e-9 >= cfg["mr_min_rr"]):       # RR dihitung ke rata-rata (TP2)
                out.append(it)
            continue
        if cfg.get("require_ote") and not kind.startswith("ara") and it.get("ote") not in ("sentuh", "baru"):
            continue                                                       # mode ketat: hanya strategi non-MR yang sedang / baru saja OTE
        if kind.startswith("ara"):                                         # ARA punya syarat tersendiri
            minimum = cfg.get("ara_early_min_score", 3.0) if kind == "ara_early" else cfg["ara_min_score"]
            if it.get("score", 0) >= minimum:
                out.append(it)
            continue
        sc = _quality(it, candles, cfg)
        if sc is not None:
            it["score"] = sc; out.append(it)
    # Either supplied bullish Four Horsemen rule creates one POTENSI alert; matching both raises priority.
    # Normal liquidity, MSS/BOS, reversal and activity conditions do not erase a matched rule.
    if "four_horsemen" in cfg.get("kinds", ()) and len(candles) >= 25:
        try:
            from screener_tags import _four_horsemen_rules
            pattern_bars = [{"date": str(x.get("date", ""))[:10], "o": float(x["open"]),
                             "h": float(x["high"]), "l": float(x["low"]), "c": float(x["close"]),
                             "v": float(x.get("volume", 0) or 0), "ohlc_complete": True} for x in candles]
            matched_rules = _four_horsemen_rules(pattern_bars)
            if matched_rules:
                highs = [float(x["high"]) for x in candles]
                lows = [float(x["low"]) for x in candles]
                closes = [float(x["close"]) for x in candles]
                volumes = [float(x.get("volume", 0) or 0) for x in candles]
                price = closes[-1]
                stop = min(lows[-4:])
                if stop >= price:
                    stop = min(lows[-4:-1]) - _tick(price)
                risk = price - stop
                if price > 0 and stop > 0 and risk > 0:
                    trigger = max(highs[-4:-1])
                    avg_volume = sum(volumes[-21:-1]) / 20.0
                    avg_value = sum(closes[i] * volumes[i] for i in range(len(candles) - 21, len(candles) - 1)) / 20.0
                    avg_range = sum(highs[i] - lows[i] for i in range(len(candles) - 21, len(candles) - 1)) / 20.0
                    fraction = _day_frac(str(candles[-1].get("date", ""))[:10])
                    relative_volume = (volumes[-1] / fraction / avg_volume) if avg_volume > 0 else 0.0
                    relative_value = ((price * volumes[-1]) / fraction / avg_value) if avg_value > 0 else 0.0
                    range_expansion = ((highs[-1] - lows[-1]) / avg_range) if avg_range > 0 else 0.0
                    bos = price > max(highs[-6:-1])
                    mss = "mss" in raw_kinds
                    reversal = bool(raw_kinds.intersection(set(REVERSAL_KINDS) | {"mr_oversold", "mr_bb_reclaim", "mr_capitulation"}))
                    score = min(5.0, 2.5 + 0.5 * (len(matched_rules) == 2)
                                + 0.75 * bool(mss or bos) + 0.75 * reversal
                                + 0.5 * (relative_volume >= 1.5) + 0.5 * (relative_value >= 1.5))
                    factors = ["aturan terpenuhi: " + "; ".join(matched_rules)]
                    confirmation = []
                    if mss: confirmation.append("MSS")
                    if bos: confirmation.append("BOS high 5 sesi")
                    if reversal: confirmation.append("setup reversal")
                    factors.append("struktur: " + (", ".join(confirmation) if confirmation else "belum ada MSS/BOS atau reversal"))
                    factors.append("ekspansi volume %.2fx dan nilai transaksi %.2fx" % (relative_volume, relative_value))
                    factors.append("rentang candle %.2fx dari rata-rata 20 sesi" % range_expansion)
                    out.append({"code": str(code).upper(), "kind": "four_horsemen", "price": price,
                                "stop": stop, "t1": price + 1.5 * risk, "t2": price + 3.0 * risk,
                                "trig": trigger, "ref": "high pola 4 Horsemen", "score": score,
                                "date": str(candles[-1].get("date", ""))[:10], "low": lows[-1],
                                "high": highs[-1], "four_horsemen_factors": factors,
                                "four_horsemen_rules": matched_rules,
                                "four_horsemen_confirmation": confirmation,
                                "relative_volume": relative_volume, "projected_value": price * volumes[-1] / fraction,
                                "scan_time": live.now_wib().strftime("%H:%M WIB"), "ax": True})
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            pass
    if out:
        try:
            fz = _amdx(candles)
        except Exception:
            fz = None
        ax = _amx(candles)
        phase_bullish = bool(_amd_buy_context(candles).get("phase_bullish"))
        for it in out:
            it["fase"] = fz; it.setdefault("ax", ax); it.setdefault("amd_phase_bullish", phase_bullish)
    return out


def scan_and_enqueue(data):
    """data: {kode: candles}. Panggil dari dashboard tiap data harga diperbarui."""
    items = []
    for code, cs in data.items():
        try:
            items += scan(str(code).upper(), cs)
        except Exception:
            continue
    return enqueue(apply_decision(items, load_cfg()))


# ---------- riwayat & statistik keberhasilan sinyal beli ----------
HIST_PATH = BASE / "signals_history.json"
HIST_BARS_PATH = BASE / "signal_bars.json"
HIST_KEEP_DAYS = 90        # riwayat disimpan sebanyak ini (hari kalender)
SIG_HORIZON = 10           # sinyal dinilai maks 10 hari bursa setelah hari sinyal
_hist_lock = threading.Lock()
_STATS = {"at": 0.0, "days": None, "data": None, "source_stamp": None}


def _hist_read():
    try:
        return list(json.loads(HIST_PATH.read_text(encoding="utf-8")).get("items", []))
    except (OSError, ValueError):
        return []


def _hist_bars_read():
    if os.environ.get("SCREENER_D1_API_URL"):
        conn = database.connect()
        try:
            out = {}
            for row in conn.execute("SELECT bars_json FROM telegram_scan_cache ORDER BY bucket"):
                try:
                    out.update(json.loads(row[0]))
                except (TypeError, ValueError):
                    continue
            return out
        finally:
            conn.close()
    try:
        data = json.loads(HIST_BARS_PATH.read_text(encoding="utf-8"))
        return data.get("bars", {}) if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _stats_source_stamp():
    stamp = []
    for path in (HIST_PATH, HIST_BARS_PATH):
        try:
            stat = path.stat()
            stamp.append((stat.st_mtime_ns, stat.st_size))
        except OSError:
            stamp.append(None)
    return tuple(stamp)


def _hist_bars_save(bars):
    """Share scanner OHLC with the web process so stats do not download the same history again."""
    if os.environ.get("SCREENER_D1_API_URL"):
        # Keep compact deterministic chunks so each D1 row stays below its 2 MB limit.
        import zlib
        grouped = {}
        for code, history in bars.items():
            bucket = zlib.crc32(str(code).encode("ascii", errors="ignore")) % 20
            grouped.setdefault(bucket, {})[code] = history
        conn = database.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.executemany(
                "INSERT INTO telegram_scan_cache(bucket,trade_day,bars_json,updated_at) VALUES(?,?,?,CURRENT_TIMESTAMP) "
                "ON CONFLICT(bucket) DO UPDATE SET trade_day=excluded.trade_day,bars_json=excluded.bars_json,updated_at=CURRENT_TIMESTAMP",
                [(bucket, _today(), json.dumps(group, separators=(",", ":"))) for bucket, group in sorted(grouped.items())],
            )
            if grouped:
                conn.execute("DELETE FROM telegram_scan_cache WHERE bucket NOT IN (%s)" % ",".join("?" for _ in grouped),
                             tuple(sorted(grouped)))
            conn.commit()
        finally:
            conn.close()
        return
    codes = {str(x.get("code", "")).upper() for x in _hist_read() if x.get("code")}
    snapshot = {code: bars[code] for code in codes if code in bars and bars[code]}
    temp = HIST_BARS_PATH.with_suffix(".json.tmp")
    try:
        temp.write_text(json.dumps({"bars": snapshot}, ensure_ascii=False), encoding="utf-8")
        temp.replace(HIST_BARS_PATH)
    except OSError:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _hist_add(row):
    """Simpan sinyal BELI terkirim (lengkap dengan harga, stop, TP) agar keberhasilannya bisa dinilai di hari-hari berikutnya."""
    if _kgrp(row.get("kind", "")) not in ("buy", "reversal"):
        return
    with _hist_lock:
        items = _hist_read()
        if any(x.get("day") == row["day"] and x.get("code") == row["code"] and x.get("kind") == row["kind"] for x in items):
            return
        items.append(row)
        cut = (live.now_wib().date() - datetime.timedelta(days=HIST_KEEP_DAYS)).isoformat()
        items = [x for x in items if x.get("day", "") >= cut]
        try:
            HIST_PATH.write_text(json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    bars = globals().get("_HIST", {}).get("bars", {})
    if bars:
        _hist_bars_save(bars)


def _eval_signal(x, bars):
    """Nilai satu sinyal beli dengan bar harian {tanggal: [o,h,l,c,v]}. Aturan konservatif:
    - Hari sinyal: jam sinyal tidak diketahui, jadi hanya close yang dipakai (high/low bisa terjadi sebelum sinyal).
    - Hari berikutnya: low <= stop -> kena stop; high >= TP1/TP2 -> tercapai. Bila stop dan TP kena di bar yang sama, dianggap stop dulu.
    - Win = TP1 tercapai sebelum stop. Maks SIG_HORIZON hari bursa setelah hari sinyal.
    -> 'tp2' | 'tp1' | 'stop' | 'open' (belum ada hasil, masih dalam horizon) | 'expired' (tak ada hasil sampai horizon) | 'nodata'"""
    stop, t1, t2, day = float(x["stop"]), float(x["t1"]), float(x["t2"]), x["day"]
    dates = sorted(d for d in bars if d >= day)
    if not dates:
        return "nodata"
    tp1 = False
    for d in dates[:SIG_HORIZON + 1]:
        _o, h, l, c, _v = bars[d]
        hi, lo = (c, c) if d == day else (h, l)
        if lo <= stop:
            return "tp1" if tp1 else "stop"
        if hi >= t1:
            tp1 = True
        if hi >= t2:
            return "tp2"
    if tp1:
        return "tp1"
    return "expired" if len(dates) > SIG_HORIZON else "open"


def signal_stats(days=30, force=False, fetch_missing=False):
    """Statistik keberhasilan sinyal beli yang pernah terkirim dalam `days` hari terakhir. Hasil di-cache 5 menit."""
    source_stamp = _stats_source_stamp()
    if (not force and _STATS["data"] is not None and _STATS["days"] == days
            and _STATS.get("source_stamp") == source_stamp and time.time() - _STATS["at"] < 300):
        return _STATS["data"]
    cut = (live.now_wib().date() - datetime.timedelta(days=days)).isoformat()
    rows = [x for x in _hist_read() if x.get("day", "") >= cut and all(x.get(k) is not None for k in ("price", "stop", "t1", "t2"))]
    bars, err = {}, None
    try:
        bars = dict(_HIST["bars"])
    except RuntimeError:
        pass
    for code, history in _hist_bars_read().items():
        if not bars.get(code):
            bars[code] = history
        else:
            bars[code].update(history)
    need = sorted({x["code"] for x in rows if not bars.get(x["code"])})
    if need and fetch_missing:
        try:
            bars.update(_fetch(need, "3mo"))
        except Exception as exc:
            err = "%s: %s" % (type(exc).__name__, exc)
    elif need:
        err = "Riwayat OHLC belum tersedia dari worker scanner."
    cnt = {k: 0 for k in ("tp2", "tp1", "stop", "open", "expired", "nodata")}
    rsum, grp = 0.0, {}
    for x in rows:
        try:
            st = _eval_signal(x, dict(bars.get(x["code"], {})))
        except Exception:
            st = "nodata"
        cnt[st] += 1
        if st in ("tp2", "tp1", "stop"):
            risk = (x["price"] - x["stop"]) or 1.0
            r = -1.0 if st == "stop" else ((x["t2"] if st == "tp2" else x["t1"]) - x["price"]) / risk
            rsum += r
            g = grp.setdefault(_grup(x["kind"]), {"name": _grup(x["kind"]), "resolved": 0, "win": 0})
            g["resolved"] += 1
            g["win"] += st != "stop"
    resolved = cnt["tp2"] + cnt["tp1"] + cnt["stop"]
    win = cnt["tp2"] + cnt["tp1"]
    groups = sorted(grp.values(), key=lambda g: -g["resolved"])
    for g in groups:
        g["winrate"] = round(g["win"] * 100.0 / g["resolved"], 1)
    data = {"ok": not bool(err), "days": days, "horizon": SIG_HORIZON, "total": len(rows), "resolved": resolved, "win": win, "tp2": cnt["tp2"],
            "stop": cnt["stop"], "open": cnt["open"], "expired": cnt["expired"], "nodata": cnt["nodata"],
            "winrate": round(win * 100.0 / resolved, 1) if resolved else None,
            "tp2rate": round(cnt["tp2"] * 100.0 / resolved, 1) if resolved else None,
            "avg_r": round(rsum / resolved, 2) if resolved else None, "groups": groups, "error": err}
    _STATS.update(at=time.time(), days=days, data=data, source_stamp=_stats_source_stamp())
    return data


def configured(cfg=None):
    cfg = cfg or load_cfg()
    return bool(cfg["token"] and str(cfg["chat_id"]).strip())


def status():
    cfg = load_cfg()
    worker = worker_lease_status()
    try:
        scan_state = json.loads(SIG_PATH.read_text(encoding="utf-8"))
        last_scan = scan_state.get("last_scan") if scan_state.get("day") == _today() else None
    except (OSError, ValueError):
        last_scan = STATE["last_scan"]
    return {"configured": configured(cfg), "enabled": bool(cfg["enabled"]) and configured(cfg) and not STATE["blocked"],
            "want_enabled": bool(cfg["enabled"]), "blocked": STATE["blocked"], "last_error": STATE["last_error"], "last_sent": STATE["last_sent"],
            "sent_today": _count_today(group="buy"), "sent_today_pot": _count_today(group="pot"), "sent_today_reversal": _count_today(group="reversal"), "last_scan": last_scan,
            "last_signals": STATE["last_signals"], "scan_error": STATE["scan_error"], "max_per_day": cfg["max_per_day"], "queued": _queued(),
            "worker_running": worker["running"], "worker_heartbeat_age": worker["heartbeat_age"]}


def _send_text(cfg, text, chat=None):
    """-> (ok, fatal, err). Menangani 429 (tunggu retry_after, 1x ulang) dan gangguan jaringan (maks 2 ulang)."""
    # Pastikan sinyal tidak pernah mengirim URL/domain yang otomatis menjadi link di Telegram.
    text = re.sub(r"(?i)\b(?:https?://|www\.)\S+|\b(?:t\.me|telegram\.me)/\S+|\b[a-z0-9.-]+\.(?:com|net|org|id|co\.id|io|gov|edu)(?:/\S*)?", "", str(text))
    tries = 0
    while True:
        tries += 1
        try:
            code, js = HTTP(cfg["token"], "sendMessage", {"chat_id": chat or cfg["chat_id"], "text": text, "disable_web_page_preview": True})
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


def _count_today_conn(conn, group=None):
    sql = "SELECT COUNT(*) FROM alert_log WHERE day=? AND status='sent'"
    params = [_today()]
    if group == "reversal":
        sql += " AND kind IN (%s)" % ",".join("?" * len(REVERSAL_KINDS)); params.extend(REVERSAL_KINDS)
    elif group == "pot":
        sql += " AND kind IN (%s)" % ",".join("?" * len(POT_KINDS)); params.extend(POT_KINDS)
    elif group == "buy":
        excluded = REVERSAL_KINDS + POT_KINDS
        sql += " AND kind NOT IN (%s)" % ",".join("?" * len(excluded)); params.extend(excluded)
    return int(conn.execute(sql, params).fetchone()[0])


def _queued_conn(conn, group=None):
    sql = "SELECT COUNT(*) FROM telegram_outbox WHERE day=? AND status IN ('pending','processing')"
    params = [_today()]
    if group == "reversal":
        sql += " AND kind IN (%s)" % ",".join("?" * len(REVERSAL_KINDS)); params.extend(REVERSAL_KINDS)
    elif group == "pot":
        sql += " AND kind IN (%s)" % ",".join("?" * len(POT_KINDS)); params.extend(POT_KINDS)
    elif group == "buy":
        excluded = REVERSAL_KINDS + POT_KINDS
        sql += " AND kind NOT IN (%s)" % ",".join("?" * len(excluded)); params.extend(excluded)
    return int(conn.execute(sql, params).fetchone()[0])


def enqueue(items):
    """Validasi sinyal dan simpan ke telegram_outbox. Tidak memulai thread atau mengirim pesan."""
    cfg = load_cfg(); skipped = {}; ok_n = 0; bn = {"buy": 0, "pot": 0, "reversal": 0}
    items = list(items or [])

    def skip(why):
        skipped[why] = skipped.get(why, 0) + 1

    if not items:
        return {"accepted": 0, "skipped": {}}
    if not configured(cfg) or not cfg["enabled"] or STATE["blocked"]:
        return {"accepted": 0, "skipped": {"notifikasi nonaktif / belum dikonfigurasi": len(items)}}
    if cfg["market_only"] and not live.market_open():
        return {"accepted": 0, "skipped": {"bursa tutup": len(items)}}

    tol = float(cfg["touch_tol_pct"]) / 100.0
    conn = database.connect()
    try:
        # Kunci tulis SQLite selama pemeriksaan kuota + insert agar dua request
        # bersamaan tidak memasukkan sinyal identik atau melewati batas harian.
        conn.execute("BEGIN IMMEDIATE")
        for it in items:
            try:
                kind = str(it.get("kind", "ote")); code = str(it["code"]).strip().upper(); price = float(it["price"])
                stop, t1, t2 = float(it["stop"]), float(it["t1"]), float(it["t2"])
                if not code:
                    raise ValueError("kode kosong")
            except (KeyError, TypeError, ValueError):
                skip("data tidak lengkap"); continue
            if kind == "ote_gagal":
                skip("sinyal OTE GAGAL telah dihentikan"); continue
            if kind not in cfg["kinds"]:
                skip("jenis sinyal nonaktif"); continue
            if cfg["live_only"] and str(it.get("date", ""))[:10] != _today():
                skip("data bukan hari ini"); continue
            g = _kgrp(kind)
            if kind == "ote":
                try:
                    zlo, zhi = float(it["lo"]), float(it["hi"])
                except (KeyError, TypeError, ValueError):
                    skip("data tidak lengkap"); continue
                dl, dh = float(it.get("low", price)), float(it.get("high", price))
                if not (dl <= zhi * (1 + tol) and dh >= zlo * (1 - tol)):
                    skip("harga belum menyentuh OTE"); continue
            if not (stop < price < t1 < t2):
                skip("level stop/target tidak valid"); continue

            existing = conn.execute(
                "SELECT id,status FROM telegram_outbox WHERE day=? AND code=? AND kind=?",
                (_today(), code, kind)).fetchone()
            if existing and existing["status"] in ("pending", "processing", "sent"):
                skip("sudah dinotifikasi hari ini" if existing["status"] == "sent" else "sudah ada di antrean"); continue

            sent_code = conn.execute(
                "SELECT COUNT(*) FROM alert_log WHERE day=? AND kind=? AND code=? AND status='sent'",
                (_today(), kind, code)).fetchone()[0]
            if sent_code >= int(cfg["per_code_per_day"]):
                skip("sudah dinotifikasi hari ini"); continue
            if _count_today_conn(conn, g) + _queued_conn(conn, g) >= _cap(cfg, g):
                skip("batas harian tercapai"); continue
            if bn[g] >= int(cfg["max_burst"]):
                skip("batas per kiriman"); continue

            keys = ("code", "kind", "price", "stop", "t1", "t2", "score", "dec", "dec_raw", "dec_adjusted",
                    "free_float_penalty", "free_float_gap_pp", "free_float_current_pct", "free_float_required_pct",
                    "free_float_deadline", "free_float_deadline_status", "free_float_as_of", "free_float_source",
                    "ote", "lo", "hi",
                    "trig", "ref", "fase", "phase", "date", "low", "high", "strategy", "name",
                    "entry_lo", "entry_hi", "entry_source", "true_open", "q1_high", "q1_low", "sweep_low",
                    "amd_reasons", "amd_context", "reversal_score", "amd_quality_score", "amd_score_detail", "amd_phase_bullish",
                    "ax", "vratio", "ara_score", "ara_stage", "ara_price", "resistance", "ara_reasons",
                    "relative_volume", "projected_value", "turnover_float", "top_gainer_score",
                    "top_gainer_candidate", "top_gainer_rank", "top_gainer_universe", "top_gainer_asof",
                    "top_gainer_reasons", "scan_time", "pre_takeoff_factors", "pre_takeoff_relative_volume",
                    "pre_takeoff_relative_value", "pre_takeoff_range_expansion", "pre_takeoff_close_position",
                    "pre_takeoff_return_pct", "pre_takeoff_data_source", "pre_takeoff_signal",
                    "four_horsemen_factors", "four_horsemen_rules", "four_horsemen_confirmation")
            payload = {k: it.get(k) for k in keys if k in it}
            encoded = json.dumps(payload, ensure_ascii=False, default=str)
            if existing:
                conn.execute("""UPDATE telegram_outbox SET payload_json=?,status='pending',attempts=0,
                    available_at=CURRENT_TIMESTAMP,locked_at=NULL,last_error='',updated_at=CURRENT_TIMESTAMP, sent_at=NULL
                    WHERE id=?""", (encoded, existing["id"]))
            else:
                conn.execute("""INSERT INTO telegram_outbox(day,code,kind,payload_json,status)
                    VALUES(?,?,?,?, 'pending')""", (_today(), code, kind, encoded))
            ok_n += 1; bn[g] += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return {"accepted": ok_n, "skipped": skipped}


def _claim_next():
    """Ambil satu pekerjaan secara atomik; aman untuk worker terpisah pada database yang sama."""
    conn = database.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        # Sinyal hari sebelumnya tidak boleh tiba-tiba dikirim setelah restart keesokan hari.
        conn.execute("""UPDATE telegram_outbox SET status='cancelled',locked_at=NULL,
            last_error='sinyal kedaluwarsa (hari bursa berganti)',updated_at=CURRENT_TIMESTAMP
            WHERE day<? AND status IN ('pending','processing')""", (_today(),))
        conn.execute("""UPDATE telegram_outbox SET status='cancelled',locked_at=NULL,
            last_error='kategori lama GAGAL OTE dihentikan; hanya setup reversal baru yang diproduksi',updated_at=CURRENT_TIMESTAMP
            WHERE kind='ote_gagal' AND status IN ('pending','processing')""")
        row = conn.execute("""SELECT * FROM telegram_outbox
            WHERE day=? AND (
              (status='pending' AND available_at<=CURRENT_TIMESTAMP) OR
              (status='processing' AND locked_at IS NOT NULL AND locked_at<=datetime('now','-15 minutes'))
            ) ORDER BY id LIMIT 1""", (_today(),)).fetchone()
        if row is None:
            conn.commit(); return None
        conn.execute("""UPDATE telegram_outbox SET status='processing',locked_at=CURRENT_TIMESTAMP,
            attempts=attempts+1,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (row["id"],))
        conn.commit()
        return {"id": row["id"], "code": row["code"], "kind": row["kind"],
                "attempts": int(row["attempts"]) + 1, "payload": json.loads(row["payload_json"])}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _set_outbox(id_, status, error="", sent=False):
    conn = database.connect()
    try:
        conn.execute("""UPDATE telegram_outbox SET status=?,locked_at=NULL,last_error=?,
            updated_at=CURRENT_TIMESTAMP,sent_at=CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE sent_at END WHERE id=?""",
            (status, str(error or "")[:500], 1 if sent else 0, id_))
        conn.commit()
    finally:
        conn.close()


def _process_outbox(job):
    it = job["payload"]
    it["kind"] = it.get("kind") or job["kind"]; it["code"] = it.get("code") or job["code"]    # payload dari dashboard bisa tanpa kind -> kartu "NULL"
    if job["kind"] == "ote_gagal":
        _set_outbox(job["id"], "cancelled", "sinyal OTE GAGAL telah dihentikan")
        return
    cfg = load_cfg(); group = _kgrp(job["kind"])
    if STATE["blocked"]:
        _set_outbox(job["id"], "failed", "pengiriman diblokir sampai konfigurasi diperbaiki")
        return
    if not configured(cfg) or not cfg["enabled"]:
        # Pause sementara; pekerjaan tidak hilang dan dapat dilanjutkan ketika notifikasi ON.
        conn = database.connect()
        try:
            conn.execute("UPDATE telegram_outbox SET status='pending',locked_at=NULL,available_at=datetime('now','+60 seconds'),last_error='notifikasi nonaktif',updated_at=CURRENT_TIMESTAMP WHERE id=?", (job["id"],))
            conn.commit()
        finally:
            conn.close()
        return
    if _count_today(group=group) >= _cap(cfg, group) or _code_today(job["code"], job["kind"]) >= int(cfg["per_code_per_day"]):
        _set_outbox(job["id"], "cancelled", "batas harian atau batas per emiten tercapai sebelum pengiriman")
        return

    ok, fatal, err = _send_text(cfg, format_message(it))
    conn = database.connect()
    try:
        if ok:
            conn.execute("INSERT INTO alert_log(code,kind,day,price,status,detail) VALUES(?,?,?,?,?,?)",
                         (job["code"], job["kind"], _today(), it.get("price"), "sent", ""))
            conn.execute("""UPDATE telegram_outbox SET status='sent',locked_at=NULL,last_error='',
                updated_at=CURRENT_TIMESTAMP,sent_at=CURRENT_TIMESTAMP WHERE id=?""", (job["id"],))
        else:
            conn.execute("INSERT INTO alert_log(code,kind,day,price,status,detail) VALUES(?,?,?,?,?,?)",
                         (job["code"], job["kind"], _today(), it.get("price"), "failed", str(err or "")[:300]))
            conn.execute("""UPDATE telegram_outbox SET status='failed',locked_at=NULL,last_error=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?""", (str(err or "")[:500], job["id"]))
        conn.commit()
    finally:
        conn.close()

    if ok:
        _sig_add(dict(it, day=_today()))
        STATE.update(last_sent=live.now_wib().isoformat(timespec="seconds"), last_error=None)
    else:
        STATE["last_error"] = err
        if fatal:
            STATE["blocked"] = True
    time.sleep(max(1.0, float(cfg["min_gap_sec"])))


def _worker(stop_event=None):
    """Worker pengirim yang membaca antrean persisten, bukan queue.Queue dalam memori."""
    stop_event = stop_event or _stop_event
    while not stop_event.is_set():
        if os.environ.get("SCREENER_TELEGRAM_WIB_WINDOW", "0").strip().lower() in ("1", "true", "yes", "on"):
            now = live.now_wib().time()
            if not (datetime.time(8, 20) <= now < datetime.time(16, 0)):
                stop_event.wait(2.0)
                continue
        try:
            job = _claim_next()
            if job is None:
                stop_event.wait(1.0)
                continue
            _process_outbox(job)
        except Exception as exc:
            STATE["last_error"] = "%s: %s" % (type(exc).__name__, exc)
            stop_event.wait(2.0)


# ---------- pemindai otomatis di server (tanpa browser / dashboard) ----------
_HIST = {"day": None, "bars": {}}
_scan_started = [False]

PRIO = [TOP_GAINER_BUY_KIND, "reversal", "ote_bounce", "mr_capitulation", "mr_bb_reclaim", "mr_oversold", "breakout_range", "breakout", "trend_pullback", "ote", "mss", "trend_cross", "momentum", "bullish"]


def _code_any_today(code):
    """Sudah ada sinyal BELI terkonfirmasi (bukan potensi / REVERSAL) untuk emiten ini hari ini?"""
    conn = database.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM alert_log WHERE day=? AND code=? AND status='sent' AND kind NOT IN (%s)" % ",".join("?" * len(REVERSAL_KINDS + POT_KINDS)),
                            [_today(), code] + list(REVERSAL_KINDS + POT_KINDS)).fetchone()[0] > 0
    finally:
        conn.close()


def _codes_and_metadata():
    conn = database.connect()
    flow_by_code = {}
    try:
        ref_date, ref = live._load_reference(conn)
        flow_dates = [r[0] for r in conn.execute(
            "SELECT data_date FROM shared_datasets WHERE dataset_type='px' AND origin='upload' "
            "AND source_filename LIKE 'Ringkasan_Saham-%' ORDER BY data_date DESC LIMIT 5"
        ).fetchall()]
        if flow_dates:
            marks = ",".join("?" for _ in flow_dates)
            sql = ("SELECT s.data_date,r.security_code,r.payload_json FROM shared_datasets s "
                   "JOIN shared_records r ON r.dataset_id=s.id WHERE s.dataset_type='px' "
                   "AND s.data_date IN (%s)" % marks)
            for item in conn.execute(sql, flow_dates).fetchall():
                try:
                    row=json.loads(item["payload_json"])
                    close,value=float(row[0] or 0),float(row[3] or 0)
                    buy,sell=float(row[5] or 0),float(row[6] or 0)
                    if close<=0 or value<=0: continue
                    flow=flow_by_code.setdefault(item["security_code"],{"net_value":0.0,"turnover":0.0,"days":0,"dates":[]})
                    flow["net_value"]+=(buy-sell)*close; flow["turnover"]+=value
                    flow["days"]+=1; flow["dates"].append(item["data_date"])
                except (TypeError,ValueError,IndexError,KeyError): continue
    finally:
        conn.close()
    if not ref: return [], {}
    codes=[c for c,a in ref.items() if len(a)>2 and a[2]>0] or list(ref)
    metadata={}
    for code,row in ref.items():
        try:
            shares=float(row[15]) if len(row)>15 else 0.0
            metadata[code]={"tradeable_shares":shares,
                            "bid_volume":float(row[14]) if len(row)>14 else 0.0,
                            "offer_volume":float(row[12]) if len(row)>12 else 0.0,
                            "bid_offer_date":ref_date}
        except (TypeError,ValueError,IndexError):
            metadata[code]={"tradeable_shares":0.0,"bid_offer_date":ref_date}
        flow=flow_by_code.get(code)
        if flow and flow["turnover"]>0:
            metadata[code].update({"foreign_flow_ratio_5d":flow["net_value"]/flow["turnover"],
                                   "foreign_flow_coverage_days":flow["days"],
                                   "foreign_flow_asof":max(flow["dates"]),
                                   "foreign_flow_from":min(flow["dates"])})
    return codes,metadata


def _codes():
    return _codes_and_metadata()[0]


def _top_gainer_scores_from_bars(metadata):
    """Score the latest Yahoo daily bars in memory; avoid rewriting thousands of D1 rows per scan."""
    from top_gainer import compute_scores

    px = {}
    for code, by_date in _HIST["bars"].items():
        ordered = sorted(by_date.items())
        previous_close = None
        for day, candle in ordered:
            try:
                op, high, low, close, volume = (float(candle[i] or 0) for i in range(5))
            except (TypeError, ValueError, IndexError):
                continue
            value = volume * (high + low + close) / 3 if volume > 0 else 0
            px.setdefault(day, {})[code] = [close, previous_close or close, volume, value,
                                             0, 0, 0, op, high, low]
            previous_close = close
    return compute_scores({"px": px}, metadata)


def _fetch(codes, period):
    """-> {kode: {tanggal: [o,h,l,c,v]}} dari yfinance."""
    import yfinance as yf
    out = {}
    for i in range(0, len(codes), 100):
        chunk = [c + ".JK" for c in codes[i:i + 100]]
        df = yf.download(chunk, period=period, interval="1d", group_by="ticker", progress=False, threads=True, auto_adjust=False)
        for t in chunk:
            try:
                sr = df[t].dropna(subset=["Close"])
            except Exception:
                continue
            for idx, r in sr.iterrows():
                out.setdefault(t[:-3], {})[idx.strftime("%Y-%m-%d")] = [float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]),
                                                                        float(r["Volume"]) if r["Volume"] == r["Volume"] else 0.0]
    return out


def scan_cycle():
    """Satu putaran: ambil data, deteksi sinyal semua emiten likuid, kirim ke antrean. Aman dipanggil berulang."""
    cfg = load_cfg()
    if not configured(cfg) or not cfg["enabled"] or STATE["blocked"]:
        return {"skipped": "nonaktif / belum dikonfigurasi"}
    if os.environ.get("SCREENER_TELEGRAM_WIB_WINDOW", "0").strip().lower() in ("1", "true", "yes", "on"):
        now = live.now_wib().time()
        if not (datetime.time(8, 20) <= now < datetime.time(16, 0)):
            return {"skipped": "di luar jendela worker WIB 08:20-16:00"}
    if cfg["market_only"] and not live.market_open():
        return {"skipped": "bursa tutup"}
    codes, metadata = _codes_and_metadata()
    if not codes:
        STATE["scan_error"] = "belum ada px resmi sebagai acuan daftar emiten"
        return {"skipped": STATE["scan_error"]}
    today = _today()
    loaded_full_history = False
    if _HIST["day"] != today or not _HIST["bars"]:
        cached = _hist_bars_read() if os.environ.get("SCREENER_D1_API_URL") else {}
        if cached:
            _HIST.update(day=today, bars=cached)
        else:
            _HIST.update(day=today, bars=_fetch(codes, "6mo"))           # cache miss: load riwayat penuh sekali
            loaded_full_history = True
    if _HIST["bars"] and not loaded_full_history:
        for c, b in _fetch(codes, "5d").items():                          # putaran berikutnya: cukup bar terbaru
            _HIST["bars"].setdefault(c, {}).update(b)
    try:
        if os.environ.get("SCREENER_D1_API_URL"):
            top_gainer_scores = _top_gainer_scores_from_bars(metadata)
        else:
            from top_gainer import current_scores
            top_gainer_scores = current_scores(metadata)
    except Exception:
        top_gainer_scores = {}
    try:
        _sig_update_now({c: b[max(b)][3] for c, b in _HIST["bars"].items() if b})        # harga kini -> ekor pergerakan di kartu sinyal
    except Exception:
        pass
    items = []
    for code, bars in _HIST["bars"].items():
        cs = [{"date": d, "open": v[0], "high": v[1], "low": v[2], "close": v[3], "volume": v[4]} for d, v in sorted(bars.items())]
        if len(cs) < 25:
            continue
        val = sum(x["close"] * x["volume"] for x in cs[-21:-1]) / 20.0
        try:
            scanned = scan(code, cs, cfg, metadata=metadata.get(code))
            if val < float(cfg["ara_min_value"]):
                scanned = [it for it in scanned if it["kind"] == "four_horsemen"]
                if not scanned:
                    continue                                              # kandidat lain tetap memakai lantai likuiditas biasa
            for it in scanned:
                radar=top_gainer_scores.get(code)
                if radar:
                    it.update({"top_gainer_score":radar["score"],"top_gainer_candidate":radar["candidate"],
                               "top_gainer_rank":radar["rank"],"top_gainer_universe":radar["universe"],
                               "top_gainer_asof":radar["asof"],"top_gainer_reasons":radar["reasons"]})
                if val < float(cfg["min_value"]) and not it["kind"].startswith("ara") and it["kind"] != "four_horsemen":
                    continue                                              # ARA boleh untuk saham lebih sepi
                it["_val"] = val; items.append(it)
            pre_takeoff = _pre_takeoff_buy(code, cs, top_gainer_scores.get(code), cfg)
            if pre_takeoff:
                pre_takeoff["_val"] = val
                items.append(pre_takeoff)
        except Exception:
            continue
    reversal_items = [it for it in items if it["kind"] in REVERSAL_KINDS]
    ara_items = [it for it in items if it["kind"].startswith("ara")]       # ARA jalur sendiri: tidak diblok sinyal beli lain di emiten yang sama
    horsemen_items = [it for it in items if it["kind"] == "four_horsemen"]
    pot_items = [it for it in items if it["kind"] in POT_KINDS and not it["kind"].startswith("ara") and it["kind"] != "four_horsemen"]
    items = [it for it in items if it["kind"] not in REVERSAL_KINDS + POT_KINDS]

    # Model B menjadi strategi utama per emiten: bila reversal AMD lolos semua filter,
    # pilih reversal itu dibanding sinyal BUY teknikal lain pada kode yang sama.
    best_rev = {}
    for it in reversal_items:
        if not _code_any_today(it["code"]) and it.get("score", 0) >= best_rev.get(it["code"], {}).get("score", -1):
            best_rev[it["code"]] = it
    items = [it for it in items if it["code"] not in best_rev]
    real_codes = {it["code"] for it in items}
    if cfg.get("one_per_code", True):                                     # satu sinyal beli terbaik per emiten, dan tidak ulang hari ini
        best = {}
        for it in items:
            k = (it.get("score", 0), -PRIO.index(it["kind"]) if it["kind"] in PRIO else -99)
            if it["code"] not in best or k > best[it["code"]][0]:
                best[it["code"]] = (k, it)
        items = [x[1] for x in best.values() if not _code_any_today(x[1]["code"])]
    bp = {}
    for it in pot_items:                                                  # satu potensi terbaik per emiten; skip bila sudah ada sinyal terkonfirmasi
        if it["code"] not in real_codes and it["code"] not in best_rev and not _code_any_today(it["code"]) and it.get("score", 0) >= bp.get(it["code"], {}).get("score", -1):
            bp[it["code"]] = it
    horsemen = {}
    for it in horsemen_items:
        if it.get("score", 0) >= horsemen.get(it["code"], {}).get("score", -1):
            horsemen[it["code"]] = it
    ARA_STAGE = {"ara_lanjut": 4, "ara_breakout": 3, "ara_potensi": 2, "ara_early": 1}
    best_ara = {}
    for it in ara_items:                                                  # satu tahap ARA terjauh per emiten (early -> potensi -> breakout -> lanjut boleh naik tahap)
        k = (ARA_STAGE.get(it["kind"], 0), it.get("score", 0))
        if it["code"] not in best_ara or k > best_ara[it["code"]][0]:
            best_ara[it["code"]] = (k, it)
    items = apply_decision(items + list(best_rev.values()) + list(bp.values()) + list(horsemen.values()) + [x[1] for x in best_ara.values()], cfg)
    last_scan = live.now_wib().isoformat(timespec="seconds")
    STATE.update(last_scan=last_scan, last_signals=len(items), scan_error=None)
    with _sig_lock:
        _sig_reload()
        _SIG["last_scan"] = last_scan
        try:
            SIG_PATH.write_text(json.dumps(_SIG, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    _hist_bars_save(_HIST["bars"])
    return enqueue(items)


def _scan_loop(stop_event=None):
    stop_event = stop_event or _stop_event
    if stop_event.wait(30):
        return
    while not stop_event.is_set():
        try:
            scan_cycle()
        except Exception as exc:
            STATE["scan_error"] = "%s: %s" % (type(exc).__name__, exc)
        stop_event.wait(max(120, int(load_cfg().get("scan_interval_sec", 600))))


def start(sender=True, scanner=True):
    """Mulai worker secara eksplisit. Aman dipanggil berulang dalam satu proses."""
    global _sender_thread, _scan_thread
    with _lifecycle_lock:
        alive = [t for t in (_sender_thread, _scan_thread) if t and t.is_alive()]
        if _stop_event.is_set() and alive:
            raise RuntimeError("Worker Telegram masih dalam proses berhenti; tunggu sebelum start ulang.")
        if _stop_event.is_set():
            _stop_event.clear()
        if sender and (_sender_thread is None or not _sender_thread.is_alive()):
            _sender_thread = threading.Thread(target=_worker, args=(_stop_event,), daemon=True, name="telegram-sender")
            _sender_thread.start()
        if scanner and (_scan_thread is None or not _scan_thread.is_alive()):
            _scan_thread = threading.Thread(target=_scan_loop, args=(_stop_event,), daemon=True, name="telegram-scanner")
            _scan_thread.start()
        return {"sender": bool(_sender_thread and _sender_thread.is_alive()),
                "scanner": bool(_scan_thread and _scan_thread.is_alive())}


def stop(timeout=5):
    """Hentikan worker dengan graceful shutdown (berguna untuk service manager/test)."""
    global _sender_thread, _scan_thread
    with _lifecycle_lock:
        _stop_event.set()
        threads = (_sender_thread, _scan_thread)
    for thread in threads:
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(0.0, float(timeout)))
    with _lifecycle_lock:
        if _sender_thread and not _sender_thread.is_alive():
            _sender_thread = None
        if _scan_thread and not _scan_thread.is_alive():
            _scan_thread = None
        return {"sender": bool(_sender_thread and _sender_thread.is_alive()),
                "scanner": bool(_scan_thread and _scan_thread.is_alive())}


def send_test():
    cfg = load_cfg()
    if not configured(cfg):
        return {"ok": False, "error": "token/chat_id belum diisi (jalankan: py telegram_setup.py)"}
    ok, fatal, err = _send_text(cfg, "Tes notifikasi screener (BELI / REVERSAL): koneksi Telegram OK.")
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


_sig_load()
# Tidak memulai worker saat import. Gunakan telegram_worker.py atau start() secara eksplisit.
