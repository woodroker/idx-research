"""Server lokal screener - sumber data tunggal: SQLite (screener.db).
Upload -> parse di server (parsers.py, setara parse() dashboard) -> simpan ke SQLite.
Dashboard membaca seluruh data dari /api/data. IndexedDB/cloud tidak lagi dipakai (hanya dibaca sekali utk migrasi).
"""
from pathlib import Path
from flask import Flask, jsonify, request, send_file, Response
from werkzeug.utils import secure_filename
import pandas as pd
import gzip, io, json, os, threading, socket, uuid, zlib

import database, free_float, fundamentals, importer, live, parsers, store, telegram

BASE = Path(__file__).resolve().parent
TEMPLATE = BASE / "templates" / "index.html"
_TAG_CACHE = {"version": None, "tags": None}
_TAG_LOCK = threading.Lock()
DATA_DIR = BASE / "data"          # arsip CSV (cadangan mentah, BUKAN sumber kalkulasi)
UPLOAD_DIR = BASE / "uploads"
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
database.initialize()

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 400 * 1024 * 1024
ALLOWED = {".xlsx", ".xls", ".csv"}
_cache = {"v": None, "raw": b"", "gz": b""}
DATA_CACHE_PATH = BASE / ".api_data_cache.gz"
_lock = threading.Lock()


def _load_disk_data_cache(version):
    """Load a version-matched gzip payload so server restarts don't rebuild 38 MB of JSON."""
    try:
        blob = DATA_CACHE_PATH.read_bytes()
        split = blob.find(b"\n")
        if split < 1 or int(blob[:split]) != version:
            return None
        gz = blob[split + 1:]
        raw = gzip.decompress(gz)
        return raw, gz
    except (OSError, ValueError, EOFError, gzip.BadGzipFile, zlib.error):
        return None


def _save_disk_data_cache(version, gz):
    """Atomically persist the compressed cache; a failed cache write must not fail the API."""
    temp_path = DATA_CACHE_PATH.with_suffix(DATA_CACHE_PATH.suffix + ".tmp")
    try:
        temp_path.write_bytes(str(version).encode("ascii") + b"\n" + gz)
        temp_path.replace(DATA_CACHE_PATH)
    except OSError:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass


def csv_text_from_upload(file_storage):
    """-> (nama_aman, teks CSV utf-8). XLSX/XLS dikonversi seperti sebelumnya (tanpa header sintetis)."""
    name = secure_filename(file_storage.filename or "upload")
    suffix = Path(name).suffix.lower()
    raw = file_storage.read()
    if suffix == ".csv":
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin1"):
            try:
                return name, raw.decode(enc)
            except UnicodeDecodeError:
                continue
        raise ValueError("Encoding CSV tidak dikenali")
    if suffix in {".xlsx", ".xls"}:
        df = pd.read_excel(io.BytesIO(raw), header=None, dtype=object)
        out = io.StringIO(newline="")
        df.to_csv(out, index=False, header=False, na_rep="")
        return name, out.getvalue()
    raise ValueError("Format file harus XLSX, XLS, atau CSV")


def process_file(f):
    """Parse + simpan satu file. Mengembalikan dict hasil (tidak melempar)."""
    orig = f.filename or "upload"
    try:
        name, text = csv_text_from_upload(f)
        keep, skipped = importer.parse_text(text, orig)
        if keep is None:
            return {"file": orig, "ok": False, "error": skipped[0]}
        if not any(x["k"] in store.PER_DATE for x in keep):
            why = "data >=1% rusak, dilewati: " + "; ".join(skipped) if skipped else "tidak ada baris data yang terbaca"
            return {"file": orig, "ok": False, "error": why}
        res = store.save_items(keep, name, origin="upload")
        # arsip mentah (cadangan) - gagal menulis arsip tidak membatalkan penyimpanan database
        try:
            tgt = DATA_DIR / (Path(name).stem + ".csv")
            tmp = tgt.with_suffix(".csv.tmp")
            tmp.write_bytes(text.encode("utf-8-sig"))
            tmp.replace(tgt)
        except OSError:
            pass
        per = [r for r in res if r["kind"] in store.PER_DATE]
        out = {"file": orig, "ok": True, "kind": per[0]["kind"], "dates": [r["date"] for r in per],
               "status": ", ".join(sorted({r["status"] for r in per})), "rows": sum(r["rows"] for r in per),
               "results": res}
        warns = [r["warning"] for r in res if r.get("warning")] + (["dilewati: " + "; ".join(skipped)] if skipped else [])
        if warns:
            out["warnings"] = warns
        return out
    except Exception as exc:                      # satu file gagal tidak menggagalkan file lain
        return {"file": orig, "ok": False, "error": str(exc)}


@app.after_request
def common_headers(response):
    if (response.mimetype == "text/html" and not response.direct_passthrough
            and "gzip" in request.headers.get("Accept-Encoding", "").lower() and response.status_code == 200):
        body = response.get_data()
        if len(body) > 1024:
            packed = gzip.compress(body, compresslevel=6)
            response.set_data(packed)
            response.headers["Content-Encoding"] = "gzip"
            response.headers["Content-Length"] = str(len(packed))
            response.headers["Vary"] = "Accept-Encoding"
    if "Cache-Control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/static/<path:fn>")
def static_files(fn):
    from flask import send_from_directory
    return send_from_directory(BASE / "static", fn)


@app.route("/")
@app.route("/original")
@app.route("/original/")
def index():
    if not TEMPLATE.exists():
        return "templates/index.html tidak ditemukan.", 500
    return send_file(TEMPLATE, mimetype="text/html")


@app.route("/api/screener/tags")
def screener_tags():
    """Tag teknikal untuk empat filter BUY/SELL; tidak tergantung status Telegram ON/OFF."""
    from screener_tags import compute_tags
    conn = database.connect()
    try:
        version = store.data_version(conn)
        # Serialisasi kalkulasi cache agar beberapa browser pertama tidak menghitung
        # seluruh tag saham bersamaan ketika versi data baru masuk.
        with _TAG_LOCK:
            if _TAG_CACHE["version"] != version or _TAG_CACHE["tags"] is None:
                raw = json.loads(store.build_data_json(conn))
                try:
                    _, metadata = telegram._codes_and_metadata()
                except Exception:
                    metadata = {}
                _TAG_CACHE["tags"] = compute_tags(raw, metadata_by_code=metadata)
                _TAG_CACHE["version"] = version
            tags = _TAG_CACHE["tags"]
        tags = dict(tags)
        try:    # Sertakan sinyal ARA terkini yang lolos scanner, termasuk emiten yang sudah masuk Top Gainer.
            telegram._sig_load()   # worker berjalan di proses lain: muat riwayat terbaru dari signals_today.json
            items = telegram.signals_today().get("items") or []
            early = set(tags.get("potensi_ara_early") or [])
            momentum = set(tags.get("potensi_ara_momentum") or [])
            ara_scores = dict(tags.get("ara_scores") or {})
            for item in items:
                code = str(item.get("code", "")).upper()
                kind = str(item.get("kind", ""))
                if not code:
                    continue
                if kind == "ara_early":
                    early.add(code)
                elif kind in ("ara_breakout", "ara_potensi", "ara_lanjut"):
                    momentum.add(code)
                if kind in ("ara_early", "ara_breakout") and item.get("ara_score") is not None:
                    ara_scores[code] = {"score": item.get("ara_score"), "kind": kind,
                                        "stage": item.get("ara_stage"), "date": item.get("date"),
                                        "ara_price": item.get("ara_price"), "reasons": item.get("ara_reasons") or []}
            tags["ara_scores"] = ara_scores
            tags["potensi_ara_early"] = sorted(early)
            tags["potensi_ara_momentum"] = sorted(momentum)
            tags["potensi_ara"] = sorted(early | momentum)
        except Exception:
            pass
        return jsonify(ok=True, data_version=version, tags=tags)
    finally:
        conn.close()


@app.route("/api/upload", methods=["POST"])
def upload():
    files = [f for f in request.files.getlist("files") if f.filename]
    if not files:
        return jsonify(ok=False, error="Tidak ada file yang dipilih"), 400
    results = [process_file(f) for f in files]
    ok = [r for r in results if r["ok"]]
    return jsonify(ok=bool(ok), results=results, saved=len(ok), failed=len(results) - len(ok),
                   note="Data diparse di server dan disimpan ke screener.db.")


@app.route("/api/data")
def get_data():
    with _lock:
        conn = database.connect()
        try:
            v = store.data_version(conn)
            if _cache["v"] != v:
                cached = _load_disk_data_cache(v)
                if cached:
                    raw, gz = cached
                else:
                    raw = store.build_data_json(conn).encode("utf-8")
                    # This is a local dashboard payload; level 1 cuts cold-cache CPU time
                    # while keeping the response compressed for the browser.
                    gz = gzip.compress(raw, compresslevel=1)
                    _save_disk_data_cache(v, gz)
                _cache.update(v=v, raw=raw, gz=gz)
        finally:
            conn.close()
        etag, raw, gz = '"v%d"' % v, _cache["raw"], _cache["gz"]
    if request.headers.get("If-None-Match") == etag:
        return Response(status=304, headers={"ETag": etag, "Cache-Control": "no-cache"})
    h = {"ETag": etag, "Cache-Control": "no-cache", "Vary": "Accept-Encoding", "Content-Type": "application/json; charset=utf-8"}
    if "gzip" in request.headers.get("Accept-Encoding", "").lower():
        h["Content-Encoding"] = "gzip"
        return Response(gz, headers=h)
    return Response(raw, headers=h)


@app.route("/api/hc", methods=["POST"])
def save_hc():
    """Jumlah saham beredar per kode & tanggal yang diisi manual di dashboard (D.hc)."""
    body = request.get_json(silent=True) or {}
    data = body.get("data")
    if not isinstance(data, dict):
        return jsonify(ok=False, error="data harus berupa objek {kode:{tanggal:jumlah}}"), 400
    try:
        res = store.save_items([{"k": "hc", "d": "-", "data": data}], "dashboard-input", origin="dashboard")
        return jsonify(ok=True, result=res[0])
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 500


@app.route("/api/migrate/legacy", methods=["POST"])
def migrate_legacy():
    """Menerima isi IndexedDB lama (array {k,d,data}) dari browser. Default mode 'fill': tidak menimpa data yang sudah ada."""
    body = request.get_json(silent=True) or {}
    items, mode = body.get("items"), body.get("mode", "fill")
    if not isinstance(items, list) or mode not in ("fill", "replace"):
        return jsonify(ok=False, error="format tidak valid"), 400
    valid = [x for x in items if isinstance(x, dict) and x.get("k") in store.ALL_KINDS and "data" in x]
    try:
        bk = database.backup("sebelum-migrasi-idb")
        res = store.save_items(valid, "indexeddb-lama", origin="idb", mode=mode)
        with database.connect() as conn:
            store.set_meta(conn, "legacy_idb_migrated", __import__("datetime").datetime.now().isoformat(timespec="seconds"))
        cnt = {}
        for r in res:
            cnt[r["status"]] = cnt.get(r["status"], 0) + 1
        return jsonify(ok=True, received=len(items), valid=len(valid), skipped_invalid=len(items) - len(valid),
                       summary=cnt, conflicts=[r for r in res if r.get("conflicts")][:50], backup=str(bk) if bk else None)
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 500


@app.route("/api/live/update", methods=["POST"])
def live_update():
    """Perbarui px dari yfinance sekarang (manual). Aturan pengaman ada di live.py."""
    res = live.update()
    return jsonify(res), (200 if res.get("ok") else 502)


def _local_user(conn):
    conn.execute("INSERT OR IGNORE INTO app_users(username,password_hash,role) VALUES('local','-','admin')")
    return conn.execute("SELECT id FROM app_users WHERE username='local'").fetchone()[0]


@app.route("/api/watchlist", methods=["GET"])
def wl_get():
    with database.connect() as conn:
        uid = _local_user(conn)
        rows = conn.execute("SELECT security_code,note FROM user_watchlists WHERE user_id=? ORDER BY id", (uid,)).fetchall()
    return jsonify(ok=True, codes=[{"code": r[0], "note": r[1]} for r in rows])


@app.route("/api/watchlist", methods=["POST"])
def wl_add():
    import re
    code = str((request.get_json(silent=True) or {}).get("code", "")).strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,6}", code):
        return jsonify(ok=False, error="kode tidak valid"), 400
    with database.connect() as conn:
        known = conn.execute("SELECT 1 FROM shared_records r JOIN shared_datasets s ON s.id=r.dataset_id "
                             "WHERE s.dataset_type='nm' AND r.security_code=?", (code,)).fetchone()
        if not known:
            return jsonify(ok=False, error="kode %s tidak ada di daftar emiten" % code), 404
        uid = _local_user(conn)
        conn.execute("INSERT OR IGNORE INTO user_watchlists(user_id,security_code) VALUES(?,?)", (uid, code))
    return jsonify(ok=True, code=code)


@app.route("/api/watchlist/<code>", methods=["DELETE"])
def wl_del(code):
    with database.connect() as conn:
        conn.execute("DELETE FROM user_watchlists WHERE user_id=? AND security_code=?", (_local_user(conn), code.upper()))
    return jsonify(ok=True)


@app.route("/api/fundamental/<code>")
def fundamental(code):
    """Fundamental per emiten dari yfinance (cache 12 jam di SQLite). PER/PBV dihitung dgn harga terakhir di database."""
    import re
    code = code.upper()
    if not re.fullmatch(r"[A-Z0-9]{2,6}", code):
        return jsonify(ok=False, error="kode tidak valid"), 400
    conn = database.connect()
    try:
        r = conn.execute("SELECT r.payload_json FROM shared_records r JOIN shared_datasets s ON s.id=r.dataset_id "
                         "WHERE s.dataset_type='px' AND r.security_code=? ORDER BY s.data_date DESC LIMIT 1", (code,)).fetchone()
    finally:
        conn.close()
    price = json.loads(r[0])[0] if r else None
    try:
        raw, status = fundamentals.get_raw(code, force=request.args.get("refresh") == "1")
    except ImportError:
        return jsonify(ok=False, error="yfinance belum terpasang (py -m pip install yfinance)"), 502
    except Exception as exc:
        return jsonify(ok=False, error=str(exc)), 502
    res = fundamentals.analyze(raw, price or raw.get("info", {}).get("currentPrice"))
    res.update(ok=True, code=code, status=status, fetched=raw.get("fetched"))
    return jsonify(res)


@app.route("/api/fundamental/cached")
def fundamental_cached():
    return jsonify(ok=True, items=fundamentals.cached_summary(), prefetch=fundamentals.prefetch_status())


@app.route("/api/fundamental/queue", methods=["POST"])
def fundamental_queue():
    codes = (request.get_json(silent=True) or {}).get("codes")
    if not isinstance(codes, list):
        return jsonify(ok=False, error="codes harus berupa daftar"), 400
    return jsonify(ok=True, added=fundamentals.enqueue(codes[:60]), prefetch=fundamentals.prefetch_status())


@app.route("/api/alerts/ote", methods=["POST"])
def alerts_ote():
    items = (request.get_json(silent=True) or {}).get("items")
    if not isinstance(items, list):
        return jsonify(ok=False, error="items harus berupa daftar"), 400
    return jsonify(ok=True, **telegram.enqueue(items[:20]))


@app.route("/api/telegram/signals")
def telegram_signals():
    return jsonify(telegram.signals_today())


@app.route("/api/telegram/signals/delete", methods=["POST"])
def telegram_signal_delete():
    b = request.get_json(silent=True) or {}
    if not b.get("code") or not b.get("kind"):
        return jsonify(ok=False, error="code & kind wajib"), 400
    return jsonify(telegram.delete_signal(b.get("code"), b.get("kind"), b.get("time")))


@app.route("/api/telegram/dash", methods=["POST"])
def telegram_dash():
    """Skor keputusan dashboard (KEP) per kode -> dipakai sebagai skor sinyal Telegram."""
    return jsonify(telegram.set_dash((request.get_json(silent=True) or {}).get("rows")))


@app.route("/api/free-float")
def free_float_data():
    cfg = telegram.load_cfg()
    rows = free_float.dashboard_data(
        today=telegram._today(), enabled=cfg.get("free_float_risk_enabled", True),
        penalty_per_pp=cfg.get("free_float_penalty_per_pp", 1.0),
        max_penalty=cfg.get("free_float_max_penalty", 10.0),
        urgency_horizon_days=cfg.get("free_float_urgency_horizon_days", 1095))
    return jsonify(ok=True, count=len(rows), today=telegram._today(), rows=rows,
                   scoring={"enabled": bool(cfg.get("free_float_risk_enabled", True)),
                            "penalty_per_pp": float(cfg.get("free_float_penalty_per_pp", 1.0)),
                            "max_penalty": float(cfg.get("free_float_max_penalty", 10.0)),
                            "urgency_horizon_days": int(cfg.get("free_float_urgency_horizon_days", 1095))})


@app.route("/api/free-float/upload", methods=["POST"])
def free_float_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(ok=False, error="Pilih file CSV free float"), 400
    if Path(f.filename).suffix.lower() != ".csv":
        return jsonify(ok=False, error="File free float harus CSV"), 400
    try:
        name, text = csv_text_from_upload(f)
        result = free_float.import_snapshot(text, name, request.form.get("as_of"))
        return jsonify(ok=True, **result)
    except (ValueError, OSError) as exc:
        return jsonify(ok=False, error=str(exc)), 400


@app.route("/api/screener/decisions")
def screener_decisions():
    """Snapshot keputusan + fase AMDX yang sama dengan UI Original, lintas proses."""
    return jsonify(ok=True, **telegram.dashboard_snapshot())


@app.route("/api/telegram/stats")
def telegram_stats():
    try:
        days = max(1, min(90, int(request.args.get("days", 30))))
    except ValueError:
        days = 30
    try:
        return jsonify(telegram.signal_stats(days, force=request.args.get("refresh") == "1"))
    except Exception as exc:
        return jsonify(ok=False, error="%s: %s" % (type(exc).__name__, exc)), 500


@app.route("/api/telegram/status")
def telegram_status():
    return jsonify(ok=True, **telegram.status())


@app.route("/api/telegram/test", methods=["POST"])
def telegram_test():
    res = telegram.send_test()
    return jsonify(res), (200 if res.get("ok") else 502)


@app.route("/api/telegram/toggle", methods=["POST"])
def telegram_toggle():
    res = telegram.toggle(bool((request.get_json(silent=True) or {}).get("enabled")))
    return jsonify(res), (200 if res.get("ok") else 400)


@app.route("/api/status")
def status():
    conn = database.connect()
    try:
        return jsonify(ok=True, schema=store.get_meta(conn, "schema_version"), data_version=store.data_version(conn),
                       summary=store.summary(conn), legacy_idb_migrated=store.get_meta(conn, "legacy_idb_migrated"),
                       csv_archive=len(list(DATA_DIR.glob("*.csv"))), live=dict(live.STATE, auto=bool(app.config.get("YF_AUTO"))), market=live.market_open(), tg=telegram.status())
    finally:
        conn.close()


@app.route("/api/csv/<path:filename>")
def get_csv(filename):
    name = Path(filename).name
    target = DATA_DIR / name
    if target.parent != DATA_DIR or not target.is_file() or target.suffix.lower() != ".csv":
        return jsonify(ok=False, error="CSV tidak ditemukan"), 404
    return send_file(target, mimetype="text/csv; charset=utf-8")


@app.route("/api/reload", methods=["POST"])
def reload_data():
    return status()


@app.route("/api/reset", methods=["POST"])
def reset_uploads():
    # Tidak menyentuh screener.db maupun arsip data/. Hanya membersihkan folder uploads sementara.
    for p in UPLOAD_DIR.iterdir():
        if p.is_file():
            p.unlink()
    return jsonify(ok=True, message="Folder uploads dibersihkan; screener.db dan arsip data/ tidak dihapus.")


if __name__ == "__main__":
    if not TEMPLATE.exists():
        raise SystemExit("File templates/index.html tidak ditemukan.")
    if os.environ.get("SCREENER_YF", "1") != "0":
        try:
            import yfinance  # noqa: F401
            app.config["YF_AUTO"] = True
            fundamentals.start_prefetch()
            live.start_background(int(os.environ.get("SCREENER_YF_INTERVAL", "300")))
            print("Auto-update harga yfinance AKTIF (tiap %s dtk selama jam bursa). Nonaktifkan: set SCREENER_YF=0" % os.environ.get("SCREENER_YF_INTERVAL", "300"))
        except ImportError:
            print("yfinance belum terpasang -> auto-update harga nonaktif (py -m pip install yfinance)")
    telegram_owner = "%s:%s:%s" % (socket.gethostname(), os.getpid(), uuid.uuid4().hex[:8])
    telegram_lease_seconds = max(30, int(os.environ.get("SCREENER_TELEGRAM_LEASE_SECONDS", "45")))
    telegram_lease_stop = threading.Event()
    telegram_started = False

    def renew_embedded_telegram_lease():
        while not telegram_lease_stop.wait(10.0):
            try:
                if not telegram.renew_worker_lease(telegram_owner, telegram_lease_seconds):
                    print("Lease Telegram hilang; menghentikan sender/scanner untuk mencegah proses ganda.", flush=True)
                    telegram.stop()
                    return
            except Exception as exc:
                print("Heartbeat lease Telegram gagal: %s" % exc, flush=True)

    worker_enabled = os.environ.get("SCREENER_TELEGRAM_WORKER", "1").strip().lower() not in ("0", "false", "no", "off")
    scanner_enabled = os.environ.get("SCREENER_TELEGRAM_SCAN", "1").strip().lower() not in ("0", "false", "no", "off")
    if worker_enabled:
        if telegram.acquire_worker_lease(telegram_owner, telegram_lease_seconds):
            state = telegram.start(sender=True, scanner=scanner_enabled)
            telegram_started = True
            threading.Thread(target=renew_embedded_telegram_lease, daemon=True, name="telegram-lease-heartbeat").start()
            print("Telegram aktif dalam proses server | sender=%s | scanner=%s" % (state["sender"], state["scanner"]), flush=True)
        else:
            print("Telegram worker eksternal sudah memegang lease; server tetap berjalan tanpa worker duplikat.", flush=True)
    print("Dashboard siap: http://127.0.0.1:5000  (database: %s)" % database.DB_PATH)
    try:
        app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
    finally:
        telegram_lease_stop.set()
        if telegram_started:
            telegram.stop()
            telegram.release_worker_lease(telegram_owner)
