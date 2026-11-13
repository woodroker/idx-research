#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backtest offline AMD BUY Quality Score Model B dari cache OHLCV proyek.

Metode konservatif:
- Sinyal dibuat ulang secara kausal: _scan_raw hanya menerima candle sampai tanggal sinyal.
- Untuk setiap kode/minggu, ambil sinyal pertama yang memenuhi ambang skor.
- Entry LIMIT di titik tengah zona FVG/OB, baru dicari mulai sesi bursa berikutnya.
- Order tidak dianggap terisi jika harga sudah membuka di bawah stop.
- Setelah terisi, stop diperiksa sebelum TP1 pada candle yang sama (asumsi konservatif OHLC harian).
- Sinyal yang tidak tersentuh dalam jendela fill dihitung sebagai unfilled, bukan win/loss.

Catatan: cache Yahoo hanya memuat harga/volume, bukan foreign flow, bid/offer, atau intraday.
Hasil ini menguji gerbang struktur dan skor Model B, bukan memvalidasi seluruh aliran dana.
"""
import argparse
import csv
import datetime as dt
import glob
import math
import pickle
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import telegram as tg


def parse_date(value):
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value)[:10])


def load_cache(path):
    with open(path, "rb") as f:
        data = pickle.load(f)
    if not isinstance(data, dict) or not data:
        raise ValueError("Cache kosong atau format tidak dikenal")
    return data


def week_key(d):
    return d - dt.timedelta(days=d.weekday())


def collect_candidates(data, fill_window, hold_window):
    candidates = []
    errors = 0
    for code, bars in data.items():
        if len(bars) < 35:
            continue
        cs = []
        for b in bars:
            cs.append({
                "date": parse_date(b["date"]).isoformat(),
                "open": float(b["open"]), "high": float(b["high"]),
                "low": float(b["low"]), "close": float(b["close"]),
                "volume": float(b.get("volume", 0) or 0),
            })
        # Sisakan hanya sinyal yang punya jendela observasi penuh.
        last_signal_i = len(cs) - fill_window - hold_window - 1
        for i in range(24, max(24, last_signal_i + 1)):
            # Setup Q1/Q2 tidak mungkin valid sebelum Rabu; hindari scan Senin/Selasa.
            if parse_date(cs[i]["date"]).weekday() < 2:
                continue
            history = cs[:i + 1]
            try:
                # Prefilter kausal: panggil scanner penuh hanya bila AMD + pullback gate lolos.
                if not tg._amd_buy_context(history).get("valid"):
                    continue
                items = tg._scan_raw(code, history)
            except Exception:
                errors += 1
                continue
            for item in items:
                if item.get("kind") != "reversal":
                    continue
                if not all(item.get(k) is not None for k in ("amd_quality_score", "entry_lo", "entry_hi", "stop", "t1")):
                    continue
                candidates.append({
                    "code": code, "date": parse_date(cs[i]["date"]), "bar_index": i,
                    "score": float(item["amd_quality_score"]),
                    "entry_lo": float(item["entry_lo"]), "entry_hi": float(item["entry_hi"]),
                    "entry_mid": (float(item["entry_lo"]) + float(item["entry_hi"])) / 2.0,
                    "stop": float(item["stop"]), "tp1": float(item["t1"]),
                    "entry_source": item.get("entry_source") or "FVG/OB",
                    "risk_pct": (float(item["price"]) - float(item["stop"])) / max(float(item["price"]), 1.0) * 100.0,
                })
    candidates.sort(key=lambda x: (x["date"], x["code"]))
    return candidates, errors


def simulate_limit(candidate, bars, fill_window, hold_window):
    i = candidate["bar_index"]
    limit_px = candidate["entry_mid"]
    stop = candidate["stop"]
    target = candidate["tp1"]
    filled_at = None
    fill_index = None
    invalidated = False

    for j in range(i + 1, min(i + fill_window + 1, len(bars))):
        b = bars[j]
        op, hi, lo = float(b["open"]), float(b["high"]), float(b["low"])
        # Gap di bawah stop lebih dulu: jangan anggap order limit yang lebih tinggi terisi.
        if op <= stop:
            invalidated = True
            break
        if lo <= limit_px <= hi or op < limit_px:
            filled_at = min(op, limit_px) if op < limit_px else limit_px
            if filled_at <= stop:
                invalidated = True
                filled_at = None
                break
            fill_index = j
            break

    if filled_at is None:
        return {"filled": 0, "invalidated": int(invalidated), "entry": None,
                "fill_date": None, "exit": "invalidated" if invalidated else "unfilled",
                "exit_date": None, "R": None, "exit_price": None, "hold_days": None}

    risk = filled_at - stop
    if risk <= 0:
        return {"filled": 0, "invalidated": 1, "entry": None,
                "fill_date": None, "exit": "invalidated", "exit_date": None,
                "R": None, "exit_price": None, "hold_days": None}

    last_j = min(fill_index + hold_window - 1, len(bars) - 1)
    for j in range(fill_index, last_j + 1):
        b = bars[j]
        op, hi, lo = float(b["open"]), float(b["high"]), float(b["low"])
        # Urutan stop-first adalah asumsi konservatif bila kedua level tersentuh dalam satu candle.
        if lo <= stop:
            px = min(op, stop) if op < stop else stop
            return {"filled": 1, "invalidated": 0, "entry": filled_at,
                    "fill_date": parse_date(bars[fill_index]["date"]).isoformat(),
                    "exit": "stop", "exit_date": parse_date(b["date"]).isoformat(),
                    "R": (px - filled_at) / risk, "exit_price": px,
                    "hold_days": j - fill_index + 1}
        if hi >= target:
            px = max(op, target) if op > target else target
            return {"filled": 1, "invalidated": 0, "entry": filled_at,
                    "fill_date": parse_date(bars[fill_index]["date"]).isoformat(),
                    "exit": "tp1", "exit_date": parse_date(b["date"]).isoformat(),
                    "R": (px - filled_at) / risk, "exit_price": px,
                    "hold_days": j - fill_index + 1}

    b = bars[last_j]
    px = float(b["close"])
    return {"filled": 1, "invalidated": 0, "entry": filled_at,
            "fill_date": parse_date(bars[fill_index]["date"]).isoformat(),
            "exit": "timeout", "exit_date": parse_date(b["date"]).isoformat(),
            "R": (px - filled_at) / risk, "exit_price": px,
            "hold_days": last_j - fill_index + 1}


def evaluate_threshold(threshold, candidates, data, fill_window, hold_window):
    selected = []
    seen = set()
    for c in candidates:
        if c["score"] < threshold:
            continue
        key = (c["code"], week_key(c["date"]))
        if key in seen:
            continue
        seen.add(key)
        selected.append(c)

    rows = []
    for c in selected:
        result = simulate_limit(c, data[c["code"]], fill_window, hold_window)
        rows.append({
            "threshold": threshold, "code": c["code"], "signal_date": c["date"].isoformat(),
            "quality_score": c["score"], "entry_lo": c["entry_lo"], "entry_hi": c["entry_hi"],
            "entry_mid": c["entry_mid"], "stop": c["stop"], "tp1": c["tp1"],
            "risk_pct": c["risk_pct"], "entry_source": c["entry_source"], **result,
        })
    trades = [r for r in rows if r["filled"] and r["R"] is not None]
    wins = sum(1 for r in trades if r["R"] > 0)
    return rows, {
        "threshold": threshold, "signals": len(rows),
        "filled": len(trades), "unfilled": sum(r["exit"] == "unfilled" for r in rows),
        "invalidated_before_fill": sum(r["exit"] == "invalidated" for r in rows),
        "fill_rate_pct": 100.0 * len(trades) / len(rows) if rows else math.nan,
        "win_rate_R_pct": 100.0 * wins / len(trades) if trades else math.nan,
        "TP1_pct": 100.0 * sum(r["exit"] == "tp1" for r in trades) / len(trades) if trades else math.nan,
        "stop_pct": 100.0 * sum(r["exit"] == "stop" for r in trades) / len(trades) if trades else math.nan,
        "timeout_pct": 100.0 * sum(r["exit"] == "timeout" for r in trades) / len(trades) if trades else math.nan,
        "avg_R": statistics.mean(r["R"] for r in trades) if trades else math.nan,
        "median_R": statistics.median(r["R"] for r in trades) if trades else math.nan,
    }


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Backtest offline Model B AMD BUY Quality Score dari cache OHLCV")
    ap.add_argument("--cache", help="file cache_*.pkl; default cache terbaru dalam hasil_backtest_amd/")
    ap.add_argument("--thresholds", default="65,70,75,80,85", help="ambang skor 0-100, dipisahkan koma")
    ap.add_argument("--fill-window", type=int, default=5, help="maks sesi untuk menunggu entry limit (default 5)")
    ap.add_argument("--hold-window", type=int, default=5, help="maks sesi setelah fill sampai exit (default 5)")
    ap.add_argument("--out", default=str(ROOT / "hasil_backtest_amd"), help="folder output CSV")
    args = ap.parse_args()

    caches = sorted(glob.glob(str(ROOT / "hasil_backtest_amd" / "cache_*.pkl")), key=lambda p: Path(p).stat().st_mtime)
    cache_path = Path(args.cache) if args.cache else (Path(caches[-1]) if caches else None)
    if not cache_path or not cache_path.exists():
        ap.error("cache tidak ditemukan; berikan --cache hasil_backtest_amd/cache_*.pkl")
    thresholds = sorted(set(float(x.strip()) for x in args.thresholds.split(",") if x.strip()))
    if not thresholds or any(x < 0 or x > 100 for x in thresholds):
        ap.error("threshold harus 0 sampai 100")
    if args.fill_window < 1 or args.hold_window < 1:
        ap.error("fill-window dan hold-window minimal 1")

    data = load_cache(cache_path)
    candidates, errors = collect_candidates(data, args.fill_window, args.hold_window)
    print("CACHE:", cache_path.name, "| saham:", len(data), "| kandidat Model B:", len(candidates), "| error scan:", errors)
    if not candidates:
        print("Tidak ada kandidat yang bisa diuji.")
        return 0

    summaries, all_rows = [], []
    for threshold in thresholds:
        rows, summary = evaluate_threshold(threshold, candidates, data, args.fill_window, args.hold_window)
        summaries.append(summary)
        all_rows.extend(rows)
    out_dir = Path(args.out)
    write_csv(out_dir / "model_b_quality_summary.csv", summaries)
    write_csv(out_dir / "model_b_quality_trades.csv", all_rows)

    print("\nAMBANG | SINYAL | FILL | FILL% | WIN R | TP1 | STOP | AVG R")
    for s in summaries:
        values = []
        for k in ("signals", "filled", "fill_rate_pct", "win_rate_R_pct", "TP1_pct", "stop_pct", "avg_R"):
            v = s[k]
            values.append(str(v) if isinstance(v, int) else ("n/a" if isinstance(v, float) and math.isnan(v) else ("%.1f%%" % v if k.endswith("pct") else "%.2f" % v)))
        print("%6.1f | %6s | %4s | %6s | %5s | %5s | %5s | %5s" % (s["threshold"], *values))
    print("\nCSV tersimpan:", out_dir / "model_b_quality_summary.csv", "dan", out_dir / "model_b_quality_trades.csv")
    print("PERINGATAN: OHLCV harian tidak memvalidasi foreign flow, bid/offer, intraday FVG/OB, atau urutan tick dalam candle.")
    print("Ambang tidak boleh dianggap teruji secara statistik bila jumlah transaksi terisi masih kecil (<30).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
