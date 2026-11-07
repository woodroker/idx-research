"""Baca/tulis dataset ke SQLite. Format dataset = {k, d, data} sama persis dengan array USR dashboard lama."""
import hashlib, json
import parsers
from database import connect

PER_DATE = ("px", "days", "tipe", "sat", "kl")
GLOBAL = ("nm", "klc", "hc")
ALL_KINDS = PER_DATE + GLOBAL


def _dump(x):
    return json.dumps(x, ensure_ascii=False, separators=(",", ":"))


def _bump(conn):
    conn.execute("UPDATE app_meta SET value=CAST(value AS INTEGER)+1 WHERE key='data_version'")


def data_version(conn):
    r = conn.execute("SELECT value FROM app_meta WHERE key='data_version'").fetchone()
    return int(r[0]) if r else 0


def get_meta(conn, key, default=None):
    r = conn.execute("SELECT value FROM app_meta WHERE key=?", (key,)).fetchone()
    return r[0] if r else default


def set_meta(conn, key, value):
    conn.execute("INSERT INTO app_meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))


def _records(k, data):
    """-> list[(code, payload_json)]"""
    if k == "klc":
        return [("", _dump(data))]
    return [(str(c), _dump(v)) for c, v in data.items()]


def _sha(k, data):
    return hashlib.sha256(_dump(data).encode("utf-8")).hexdigest()


def save_item(conn, k, d, data, filename, origin="upload", mode="replace", user_id=None):
    """Simpan satu dataset. Mengembalikan dict status.
    mode='replace' : jenis+tanggal sama ditimpa (aturan dashboard lama).
    mode='yf'      : khusus pembaruan yfinance: hanya boleh mengisi tanggal kosong atau mengganti dataset yang juga berasal dari yfinance.
    mode='fill'    : hanya mengisi yang belum ada; yang sudah ada & berbeda dicatat sebagai konflik, TIDAK ditimpa.
    nm / hc / klc (global) digabung per kode (nm,hc) atau diganti (klc)."""
    if k not in ALL_KINDS:
        raise ValueError("jenis dataset tidak dikenal: %r" % k)
    d = "-" if k in GLOBAL else str(d)
    if k in PER_DATE and not (len(d) == 10 and d[4] == "-" and d[7] == "-"):
        raise ValueError("tanggal tidak valid untuk %s: %r" % (k, d))
    row = conn.execute("SELECT id,content_sha256,row_count,origin FROM shared_datasets WHERE dataset_type=? AND data_date=?", (k, d)).fetchone()

    if k in ("nm", "hc"):    # gabung per kode
        if not data:
            return {"kind": k, "date": d, "status": "kosong", "rows": 0}
        if row is None:
            cur = conn.execute("INSERT INTO shared_datasets(dataset_type,source_filename,data_date,content_sha256,row_count,origin,parser_version) VALUES(?,?,?,?,0,?,?)",
                               (k, filename, d, "", origin, parsers.PARSER_VERSION))
            ds = cur.lastrowid
        else:
            ds = row["id"]
        added = changed = same = 0
        for code, payload in _records(k, data):
            ex = conn.execute("SELECT id,payload_json FROM shared_records WHERE dataset_id=? AND security_code=?", (ds, code)).fetchone()
            if ex is None:
                conn.execute("INSERT INTO shared_records(dataset_id,security_code,record_date,payload_json) VALUES(?,?,?,?)", (ds, code, d, payload)); added += 1
            elif ex["payload_json"] == payload:
                same += 1
            elif mode == "replace":
                conn.execute("UPDATE shared_records SET payload_json=? WHERE id=?", (payload, ex["id"])); changed += 1
            else:
                changed += 1   # konflik tercatat, tidak ditimpa
        n = conn.execute("SELECT COUNT(*) FROM shared_records WHERE dataset_id=?", (ds,)).fetchone()[0]
        conn.execute("UPDATE shared_datasets SET row_count=?, imported_at=CURRENT_TIMESTAMP WHERE id=?", (n, ds))
        if added or (changed and mode == "replace"):
            _bump(conn)
        return {"kind": k, "date": d, "status": "digabung" if (added or (changed and mode == "replace")) else "tidak berubah",
                "rows": n, "added": added, "changed": changed if mode == "replace" else 0,
                "conflicts": changed if mode == "fill" else 0}

    sha = _sha(k, data)
    recs = _records(k, data)
    if mode == "yf" and row is not None and row["origin"] != "yfinance":
        return {"kind": k, "date": d, "status": "dilindungi", "rows": row["row_count"]}
    if row is not None:
        if row["content_sha256"] == sha:
            return {"kind": k, "date": d, "status": "tidak berubah", "rows": row["row_count"]}
        if mode == "fill":
            return {"kind": k, "date": d, "status": "konflik", "rows": row["row_count"], "new_rows": len(recs),
                    "conflicts": 1}
    warn = None
    if row is not None:
        if len(recs) < row["row_count"]:
            warn = "jumlah baris turun %d -> %d (periksa apakah file parsial)" % (row["row_count"], len(recs))
        if not (mode == "yf" and row["origin"] == "yfinance"):   # pembaruan rutin yfinance tidak memenuhi audit_log
          conn.execute("INSERT INTO audit_log(actor_user_id,action,target,details_json) VALUES(?,?,?,?)",
                     (user_id, "dataset_replaced", "%s|%s" % (k, d),
                      _dump({"old_sha": row["content_sha256"], "old_rows": row["row_count"], "new_sha": sha,
                             "new_rows": len(recs), "file": filename, "origin": origin})))
        conn.execute("DELETE FROM shared_datasets WHERE id=?", (row["id"],))      # records ikut terhapus (CASCADE)
    cur = conn.execute("INSERT INTO shared_datasets(dataset_type,source_filename,data_date,content_sha256,row_count,imported_by,origin,parser_version) VALUES(?,?,?,?,?,?,?,?)",
                       (k, filename, d, sha, len(recs), user_id, origin, parsers.PARSER_VERSION))
    conn.executemany("INSERT INTO shared_records(dataset_id,security_code,record_date,payload_json) VALUES(?,?,?,?)",
                     [(cur.lastrowid, c, d, p) for c, p in recs])
    _bump(conn)
    out = {"kind": k, "date": d, "status": "diganti" if row is not None else "baru", "rows": len(recs)}
    if warn:
        out["warning"] = warn
    return out


def save_items(items, filename, origin="upload", mode="replace", user_id=None):
    """Satu transaksi untuk seluruh item (semua tersimpan atau tidak sama sekali)."""
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        res = [save_item(conn, x["k"], x.get("d", "-"), x["data"], filename, origin, mode, user_id) for x in items]
        conn.execute("COMMIT")
        return res
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def build_data_json(conn):
    """Teks JSON struktur D {px,days,tipe,sat,kl,nm,klc,hc} - dirangkai langsung dari payload agar cepat."""
    parts = []
    for k in PER_DATE:
        dsets = conn.execute("SELECT id,data_date FROM shared_datasets WHERE dataset_type=? ORDER BY data_date", (k,)).fetchall()
        inner = []
        for ds in dsets:
            recs = conn.execute("SELECT security_code,payload_json FROM shared_records WHERE dataset_id=? ORDER BY id", (ds["id"],)).fetchall()
            inner.append('%s:{%s}' % (_dump(ds["data_date"]), ",".join('%s:%s' % (_dump(r[0]), r[1]) for r in recs)))
        parts.append('"%s":{%s}' % (k, ",".join(inner)))
    for k in ("nm", "hc"):
        rows = conn.execute("SELECT r.security_code,r.payload_json FROM shared_records r JOIN shared_datasets s ON s.id=r.dataset_id "
                            "WHERE s.dataset_type=? ORDER BY r.id", (k,)).fetchall()
        parts.append('"%s":{%s}' % (k, ",".join('%s:%s' % (_dump(r[0]), r[1]) for r in rows)))
    r = conn.execute("SELECT r.payload_json FROM shared_records r JOIN shared_datasets s ON s.id=r.dataset_id WHERE s.dataset_type='klc' LIMIT 1").fetchone()
    parts.append('"klc":%s' % (r[0] if r else "[]"))
    return "{" + ",".join(parts) + "}"


def summary(conn):
    out = {}
    for r in conn.execute("SELECT dataset_type k, COUNT(*) n, MIN(data_date) lo, MAX(data_date) hi, SUM(row_count) rows FROM shared_datasets GROUP BY 1 ORDER BY 1"):
        out[r["k"]] = {"datasets": r["n"], "first": r["lo"], "last": r["hi"], "records": r["rows"]}
    return out
