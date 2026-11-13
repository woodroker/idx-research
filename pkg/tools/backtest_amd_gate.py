#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKTEST GERBANG AMDX BUY  -  Model C (terpakai di upgrade Anda)
=================================================================
Skrip BARU & terpisah. Tidak mengubah file apa pun di proyek screener Anda.
Hanya menguji gerbang Model C PERSIS (candle terakhir Rabu-Jumat, sweep Selasa,
close di atas High & Close Selasa, close masih di dalam range Senin (Q1), range Q1
antara 0,25-2,2 x ATR, + syarat fase bullish dari telegram._amd_buy_context).

Cara kerja:
  - Untuk tiap saham & tiap minggu, diambil sinyal PERTAMA yang lolos gerbang.
  - Entry default = open hari berikutnya; --entry close tersedia hanya untuk pembanding yang optimistis.
  - Stop = low Selasa - 0,1 x ATR14 ; TP1 = High Senin atau minimal 1,5R (sama dengan rancangan Model C).
  - Hasil dilihat sampai 5 hari bursa ke depan: return +1/+3/+5 hari, dan simulasi R (stop/TP1/timeout).
  - Pembanding (baseline): semua saham-hari Rabu-Jumat tanpa gerbang.

Pemakaian (Windows, dari folder proyek Anda):
    py -m pip install yfinance pandas
    py tools\\backtest_amd_gate.py                                  # otomatis memakai folder proyek
    py tools\\backtest_amd_gate.py --top 450 --months 12
    py tools\\backtest_amd_gate.py --codes-file kode.txt            # daftar kode sendiri (tanpa .JK)

Hasil: folder hasil_backtest_amd/ (sinyal.csv, ringkasan.csv) + ringkasan di layar.
Catatan: data Yahoo tidak resmi & ada keterlambatan; hasil backtest bukan jaminan hasil nyata.
"""
import argparse
import csv
import datetime as dt
import glob
import math
import os
import pickle
import random
import statistics
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # folder proyek (skrip ini ada di tools/)
HORIZONS = (1, 3, 5)
H_MAX = 5


# --------------------------------------------------------------------------- data
def load_universe(args):
    if args.codes_file:
        with open(args.codes_file, encoding="utf-8-sig") as f:
            codes = [x.strip().upper().replace(".JK", "") for x in f if x.strip()]
        return list(dict.fromkeys(codes))
    path = args.csv
    if not path:
        here = ROOT_DIR
        found = sorted(glob.glob(os.path.join(here, "data", "Ringkasan_Saham-*.csv")))
        if not found:
            sys.exit("Tidak menemukan data/Ringkasan_Saham-*.csv. Pakai --csv <file> atau --codes-file <file>.")
        path = found[-1]
    import pandas as pd
    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    df = df.dropna(subset=["Kode Saham"])
    if "Nilai" in df.columns:
        df["Nilai"] = pd.to_numeric(df["Nilai"], errors="coerce").fillna(0)
        df = df.sort_values("Nilai", ascending=False)
    codes = [str(c).strip().upper() for c in df["Kode Saham"] if str(c).strip()]
    codes = list(dict.fromkeys(codes))
    print("Universe dari %s : %d kode, dipakai %d paling likuid." % (os.path.basename(path), len(codes), min(args.top, len(codes))))
    return codes[: args.top]


def clean_bars(df):
    import pandas as pd
    out = []
    if df is None or len(df) == 0:
        return out
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = pd.to_datetime(df.index)
    try:
        idx = idx.tz_localize(None)
    except (TypeError, AttributeError):
        pass
    for d, (_, r) in zip(idx, df.iterrows()):
        o, h, l, c = float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"])
        v = float(r["Volume"]) if "Volume" in df.columns and r["Volume"] == r["Volume"] else 0.0
        if c <= 0 or h < l or v <= 0:
            continue                                    # hari tanpa transaksi / data rusak dilewati
        out.append({"date": d.date(), "open": o or c, "high": h, "low": l, "close": c, "volume": v})
    out.sort(key=lambda b: b["date"])
    return out


def download(codes, start, end, cache_file, refresh):
    if os.path.exists(cache_file) and not refresh:
        with open(cache_file, "rb") as f:
            data = pickle.load(f)
        print("Memakai cache %s (%d saham). Tambah --refresh untuk mengunduh ulang." % (cache_file, len(data)))
        return data
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("Butuh yfinance:  py -m pip install yfinance pandas")
    data = {}
    batch = 40
    for k in range(0, len(codes), batch):
        part = codes[k:k + batch]
        tick = [c + ".JK" for c in part]
        print("Unduh %d-%d dari %d ..." % (k + 1, min(k + batch, len(codes)), len(codes)))
        df = None
        for attempt in (1, 2):
            try:
                df = yf.download(tick, start=start.isoformat(), end=end.isoformat(), auto_adjust=False,
                                 group_by="ticker", threads=True, progress=False)
                break
            except Exception as e:                      # jaringan / limit Yahoo
                print("  gagal (%s), percobaan %d" % (e, attempt))
        if df is None or len(df) == 0:
            continue
        for c in part:
            try:
                sub = df[c + ".JK"] if len(part) > 1 else df
                bars = clean_bars(sub)
            except Exception:
                bars = []
            if len(bars) >= 40:
                data[c] = bars
    with open(cache_file, "wb") as f:
        pickle.dump(data, f)
    print("Berhasil: %d saham dengan data cukup." % len(data))
    return data


def make_demo(n_codes, end, months, seed=7):
    """Data acak (random walk) HANYA untuk menguji skrip tanpa internet. Hasilnya tidak bermakna."""
    rnd = random.Random(seed)
    days = int(months * 30.44) + 90
    dates = [end - dt.timedelta(days=k) for k in range(days, 0, -1)]
    dates = [d for d in dates if d.isoweekday() <= 5]
    data = {}
    for i in range(n_codes):
        px, bars = 1000 * (1 + rnd.random() * 5), []
        for d in dates:
            o = px * (1 + rnd.gauss(0, 0.008))
            c = o * (1 + rnd.gauss(0, 0.02))
            h = max(o, c) * (1 + abs(rnd.gauss(0, 0.01)))
            l = min(o, c) * (1 - abs(rnd.gauss(0, 0.01)))
            bars.append({"date": d, "open": o, "high": h, "low": l, "close": c, "volume": 1e6})
            px = c
        data["DEMO%03d" % i] = bars
    return data


# --------------------------------------------------------------------------- gerbang
def week_key(d):
    return d.toordinal() - d.weekday()


def wilder_atr_series(bars):
    """ATR Wilder, rekurensi yang sama dengan telegram._amd_buy_context (kausal -> aman dihitung sekali)."""
    trs, atrs, prev = [], [], None
    for b in bars:
        tr = b["high"] - b["low"] if prev is None else max(b["high"] - b["low"], abs(b["high"] - prev), abs(b["low"] - prev))
        trs.append(tr)
        if len(atrs) < 14:
            atrs.append(sum(trs) / len(trs))
        else:
            atrs.append((atrs[-1] * 13 + tr) / 14)
        prev = b["close"]
    return atrs


def week_context(bars, i):
    last = bars[i]
    wk = week_key(last["date"])
    mon = tue = None
    mon_i = None
    j = i
    while j >= 0 and week_key(bars[j]["date"]) == wk:
        wd = bars[j]["date"].isoweekday()
        if wd == 1:
            mon, mon_i = bars[j], j
        elif wd == 2:
            tue = bars[j]
        j -= 1
    return mon, tue, mon_i


def gate_B(bars, i, atrs):
    if i + 1 < 20:
        return None
    last = bars[i]
    if last["date"].isoweekday() < 3:
        return None
    mon, tue, mon_i = week_context(bars, i)
    if not (mon and tue):
        return None
    q1_atr = max(1.0, atrs[mon_i])
    q1_range = mon["high"] - mon["low"]
    q1_ok = 0.25 * q1_atr <= q1_range <= 2.2 * q1_atr
    swept = tue["low"] < mon["low"] and tue["close"] > mon["low"]
    mss = last["close"] > tue["high"] and last["close"] > tue["close"]
    reclaimed = mss and mon["low"] <= last["close"] <= mon["high"]
    if q1_ok and swept and reclaimed and mss:
        return mon, tue
    return None


def make_gate_BX(modelc_dir, pullback=True):
    sys.path.insert(0, os.path.abspath(modelc_dir))
    try:
        import telegram as tg                            # modul Model C (hanya dibaca, tidak diubah)
        fn = tg._amd_buy_context
    except Exception as e:
        print("PERINGATAN: gagal memuat telegram.py dari %s (%s). Gerbang BX dilewati." % (modelc_dir, e))
        return None

    def gate_BX(bars, i, atrs):
        g = gate_B(bars, i, atrs)                       # valid Model C = syarat B + fase bullish -> hemat panggilan
        if not g:
            return None
        cs = [{"date": b["date"].isoformat(), "open": b["open"], "high": b["high"], "low": b["low"],
               "close": b["close"], "volume": b["volume"]} for b in bars[max(0, i - 450): i + 1]]
        try:
            r = fn(cs)
        except Exception:
            return None
        if not r or not r.get("phase_bullish"):
            return None
        if pullback and not r.get("pullback_ok"):       # konteks pullback: close <= REV_MAX_HI20 x high 20 hari
            return None
        return g
    return gate_BX


# --------------------------------------------------------------------------- simulasi
def simulate(bars, i, entry, stop, tp, hmax=H_MAX, cost_rate=0.0):
    risk = entry - stop
    for k in range(1, hmax + 1):
        b = bars[i + k]
        if b["low"] <= stop:
            ex = min(b["open"], stop) if b["open"] < stop else stop
            return (ex * (1 - cost_rate) - entry * (1 + cost_rate)) / risk, "stop", k
        if b["high"] >= tp:
            ex = max(b["open"], tp) if b["open"] >= tp else tp
            return (ex * (1 - cost_rate) - entry * (1 + cost_rate)) / risk, "tp1", k
    ex = bars[i + hmax]["close"]
    return (ex * (1 - cost_rate) - entry * (1 + cost_rate)) / risk, "timeout", hmax


def net_return(exit_price, entry, cost_rate):
    """Net long return after proportional buy and sell costs, on cash spent including buy cost."""
    if entry <= 0:
        return float("nan")
    return exit_price * (1 - cost_rate) / (entry * (1 + cost_rate)) - 1


def run_gate(name, gate, data, atr_map, eval_start, args):
    rows = []
    for code, bars in data.items():
        atrs = atr_map[code]
        seen = set()
        for i in range(len(bars)):
            d = bars[i]["date"]
            if d < eval_start or d.isoweekday() < 3:
                continue
            wk = week_key(d)
            if wk in seen:
                continue
            g = gate(bars, i, atrs)
            if not g:
                continue
            seen.add(wk)                                 # sinyal pertama per saham per minggu
            mon, tue = g
            row = {"gate": name, "code": code, "week": dt.date.fromordinal(wk).isoformat(),
                   "signal_date": d.isoformat(), "evaluable": 0,
                   "cost_bps_per_side": args.cost_bps_per_side}
            if i + H_MAX < len(bars):
                entry = bars[i]["close"] if args.entry == "close" else bars[i + 1]["open"]
                stop = tue["low"] - args.stop_buffer_atr * atrs[i]
                risk = entry - stop
                if risk > 0:
                    tp = entry + args.tp1_r * risk if args.tp1_r > 0 else max(mon["high"], entry + 1.5 * risk)
                    cost_rate = args.cost_bps_per_side / 10000.0
                    R, why, days = simulate(bars, i, entry, stop, tp, cost_rate=cost_rate)
                    row.update(evaluable=1, entry=round(entry, 2), stop=round(stop, 2), tp1=round(tp, 2),
                               R=round(R, 4), exit=why, exit_days=days)
                    for h in HORIZONS:
                        row["ret%d" % h] = round(net_return(bars[i + h]["close"], entry, cost_rate), 5)
            rows.append(row)
    return rows


def baseline(data, eval_start, args):
    acc = {h: [] for h in HORIZONS}
    for code, bars in data.items():
        for i in range(len(bars)):
            d = bars[i]["date"]
            if d < eval_start or d.isoweekday() < 3 or i + H_MAX >= len(bars):
                continue
            entry = bars[i]["close"] if args.entry == "close" else bars[i + 1]["open"]
            cost_rate = args.cost_bps_per_side / 10000.0
            for h in HORIZONS:
                acc[h].append(net_return(bars[i + h]["close"], entry, cost_rate))
    return acc


# --------------------------------------------------------------------------- statistik
def mean_ci(xs):
    n = len(xs)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(xs) / n
    if n < 2:
        return m, float("nan")
    sd = statistics.stdev(xs)
    return m, 1.96 * sd / math.sqrt(n)


def welch_z(a, b):
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    va, vb = statistics.variance(a), statistics.variance(b)
    se = math.sqrt(va / len(a) + vb / len(b))
    return (sum(a) / len(a) - sum(b) / len(b)) / se if se > 0 else float("nan")


def pct(x):
    return "   n/a " if x != x else "%+6.2f%%" % (x * 100)


def summarize(name, rows, weeks):
    ev = [r for r in rows if r["evaluable"]]
    s = {"gate": name, "sinyal": len(rows), "evaluable": len(ev), "per_minggu": len(rows) / weeks if weeks else float("nan")}
    for h in HORIZONS:
        xs = [r["ret%d" % h] for r in ev]
        s["win%d" % h] = (sum(1 for x in xs if x > 0) / len(xs)) if xs else float("nan")
        s["mean%d" % h], s["ci%d" % h] = mean_ci(xs)
        s["med%d" % h] = statistics.median(xs) if xs else float("nan")
    Rs = [r["R"] for r in ev]
    s["avgR"], s["ciR"] = mean_ci(Rs)
    s["winR"] = (sum(1 for x in Rs if x > 0) / len(Rs)) if Rs else float("nan")
    for k in ("tp1", "stop", "timeout"):
        s["exit_" + k] = (sum(1 for r in ev if r["exit"] == k) / len(ev)) if ev else float("nan")
    return s, Rs, [r["ret5"] for r in ev]


def main():
    ap = argparse.ArgumentParser(description="Backtest gerbang AMDX BUY Model C")
    ap.add_argument("--months", type=float, default=6, help="lama pengujian dalam bulan (default 6)")
    ap.add_argument("--top", type=int, default=450, help="jumlah saham paling likuid dari CSV Ringkasan (default 450)")
    ap.add_argument("--csv", help="file Ringkasan_Saham-*.csv (default: yang terbaru di data/)")
    ap.add_argument("--codes-file", help="file teks berisi kode saham, satu per baris")
    ap.add_argument("--modelc", default=ROOT_DIR, help="folder yang berisi telegram.py (default: folder proyek)")
    ap.add_argument("--tp1-r", type=float, default=0.75, help="TP1 sebagai kelipatan R (default 0.75 = sama dengan telegram.REV_TP1_R; 0 = aturan lama High Senin / 1,5R)")
    ap.add_argument("--entry", choices=("close", "next_open"), default="next_open")
    ap.add_argument("--cost-bps-per-side", type=float, default=0.0,
                    help="biaya + slippage per sisi dalam basis poin; default 0 = hasil kotor (mis. 25 untuk skenario biaya 0,25%% per sisi)")
    ap.add_argument("--stop-buffer-atr", type=float, default=0.1)
    ap.add_argument("--end", help="tanggal akhir YYYY-MM-DD (default hari ini)")
    ap.add_argument("--out", default=os.path.join(ROOT_DIR, "hasil_backtest_amd"))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--demo", action="store_true", help="data acak untuk uji skrip tanpa internet (hasil tidak bermakna)")
    args = ap.parse_args()
    if args.cost_bps_per_side < 0:
        ap.error("--cost-bps-per-side tidak boleh negatif")

    end = dt.date.fromisoformat(args.end) if args.end else dt.date.today()
    eval_start = end - dt.timedelta(days=int(args.months * 30.44))
    dl_start = eval_start - dt.timedelta(days=75)       # pemanasan ATR / struktur minggu
    os.makedirs(args.out, exist_ok=True)

    if args.demo:
        data = make_demo(80, end, args.months)
        print("MODE DEMO: data acak, hanya untuk menguji skrip.")
    else:
        codes = load_universe(args)
        cache = os.path.join(args.out, "cache_%s_%d.pkl" % (end.strftime("%Y%m%d"), len(codes)))
        data = download(codes, dl_start, end + dt.timedelta(days=1), cache, args.refresh)
    if not data:
        sys.exit("Tidak ada data harga yang berhasil diunduh.")

    atr_map = {c: wilder_atr_series(b) for c, b in data.items()}
    weeks = len({week_key(b["date"]) for bars in data.values() for b in bars if b["date"] >= eval_start})
    gx = make_gate_BX(args.modelc)
    if not gx:
        sys.exit("Gagal memuat gerbang Model C dari --modelc. Periksa path telegram.py di folder itu.")
    gx_old = make_gate_BX(args.modelc, pullback=False)
    gates = [("Model C lama (tanpa filter pullback)", gx_old), ("Model C + filter pullback (baru)", gx)]

    print("\nPeriode uji: %s s/d %s  |  %d saham  |  %d minggu  |  entry=%s  |  biaya=%g bps/sisi" %
          (eval_start, end, len(data), weeks, args.entry, args.cost_bps_per_side))
    all_rows, summaries, Rmap, R5map = [], [], {}, {}
    for name, g in gates:
        rows = run_gate(name, g, data, atr_map, eval_start, args)
        all_rows += rows
        s, Rs, r5 = summarize(name, rows, weeks)
        summaries.append(s)
        Rmap[name], R5map[name] = Rs, r5

    base = baseline(data, eval_start, args)

    print("\n=== RETURN SETELAH SINYAL (dari harga entry) ===")
    print("%-40s %6s %6s | %-24s | %-24s | %-24s" % ("gerbang", "sinyal", "/mgg", "+1 hari  win%   rata2", "+3 hari  win%   rata2", "+5 hari  win%   rata2"))
    for s in summaries:
        cells = ["%5.1f%% %s" % (s["win%d" % h] * 100, pct(s["mean%d" % h])) for h in HORIZONS]
        print("%-40s %6d %6.1f | %-24s | %-24s | %-24s" % (s["gate"], s["sinyal"], s["per_minggu"], *cells))
    bcells = []
    for h in HORIZONS:
        xs = base[h]
        w = sum(1 for x in xs if x > 0) / len(xs) if xs else float("nan")
        bcells.append("%5.1f%% %s" % (w * 100, pct(sum(xs) / len(xs) if xs else float("nan"))))
    print("%-40s %6s %6s | %-24s | %-24s | %-24s" % ("PEMBANDING: semua saham-hari Rab-Jum", "-", "-", *bcells))

    print("\n=== SIMULASI STOP / TP1 (maks 5 hari bursa, stop dianggap kena lebih dulu bila satu candle menyentuh keduanya) ===")
    print("%-40s %8s %8s %12s %7s %7s %8s" % ("gerbang", "dievalu", "win R>0", "rata2 R (±95%)", "TP1", "stop", "timeout"))
    for s in summaries:
        print("%-40s %8d %7.1f%% %+6.2f ±%-5.2f %6.1f%% %6.1f%% %7.1f%%" % (
            s["gate"], s["evaluable"], s["winR"] * 100, s["avgR"], s["ciR"] if s["ciR"] == s["ciR"] else 0,
            s["exit_tp1"] * 100, s["exit_stop"] * 100, s["exit_timeout"] * 100))

    print("\n=== PEMISAHAN WAKTU (cek overfit): paruh awal vs paruh akhir periode uji ===")
    mid = eval_start + (end - eval_start) / 2
    for name in [g[0] for g in gates]:
        ev = [r for r in all_rows if r["gate"] == name and r["evaluable"]]
        for lab, part in (("awal ", [r for r in ev if r["signal_date"] < mid.isoformat()]), ("akhir", [r for r in ev if r["signal_date"] >= mid.isoformat()])):
            if part:
                print("%-40s %s n=%3d  TP1 %5.1f%%  stop %5.1f%%  win R>0 %5.1f%%  rata2 R %+.2f" % (
                    name, lab, len(part), 100.0 * sum(1 for r in part if r["exit"] == "tp1") / len(part),
                    100.0 * sum(1 for r in part if r["exit"] == "stop") / len(part),
                    100.0 * sum(1 for r in part if r["R"] > 0) / len(part), sum(r["R"] for r in part) / len(part)))

    print("\nCATATAN PENTING:")
    print(" - Sinyal dalam satu minggu yang sama saling berkorelasi (kondisi pasar sama), jadi selang kepercayaan di atas terlalu optimis.")
    print(" - Entry default memakai open sesi berikutnya. Ini masih proxy OHLC harian, bukan bukti fill.")
    if args.cost_bps_per_side:
        print(" - Return dan R sudah dikurangi biaya + slippage asumsi %g bps pada tiap sisi; sesuaikan dengan broker dan likuiditas Anda." % args.cost_bps_per_side)
    else:
        print(" - Biaya transaksi/slippage = 0 bps; hasil yang ditampilkan kotor. Gunakan --cost-bps-per-side sesuai broker dan likuiditas Anda.")
    print(" - Semesta default berasal dari snapshot Ringkasan terbaru, sehingga bias survivorship mungkin terjadi; data emiten delisting historis belum tersedia di sumber ini.")
    print(" - Hanya ~%d minggu data. Jumlah sinyal kecil (<30) = hasil belum bisa dipercaya." % weeks)

    with open(os.path.join(args.out, "sinyal.csv"), "w", newline="", encoding="utf-8") as f:
        cols = ["gate", "code", "week", "signal_date", "evaluable", "cost_bps_per_side", "entry", "stop", "tp1", "R", "exit", "exit_days", "ret1", "ret3", "ret5"]
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    with open(os.path.join(args.out, "ringkasan.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        w.writeheader()
        w.writerows(summaries)
    print("\nTersimpan: %s/sinyal.csv  dan  %s/ringkasan.csv" % (args.out, args.out))


if __name__ == "__main__":
    main()
