#!/usr/bin/env python3
"""Walk-forward study of next-session IDX top gainers using SQLite history.

The primary label uses next-session open-to-close return as a daily-OHLC tradability proxy; it does not model actual opening fills.

All predictors are restricted to information available at the signal close.
The daily >=5% holder-flow feature uses dataset dates strictly before the signal.
This is research output only; it does not change the live screener score.
"""
from __future__ import annotations

import csv
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "screener.db"
OUT = ROOT / "hasil_backtest_amd" / "top_gainer_20261112_openclose_proxy"
MIN_AVG_VALUE = 250_000_000  # Rp; configurable below
TOP_GAINER_SHARE = 0.20      # top 20% of positive next-session open-to-close returns
FEE_PER_SIDE = 0.0025        # 15 bps fee + 10 bps slippage, each side

TECH = ["ret_1d", "ret_5d", "ret_20d", "log_value_ratio", "log_volume_ratio", "close_position"]
MARKET = TECH + ["foreign_net_value_ratio_5d", "bid_imbalance_5d"]
FULL = MARKET + ["holder_net_shares_pct_5d"]


def read_db():
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    dates = [r[0] for r in con.execute("SELECT data_date FROM shared_datasets WHERE dataset_type='px' ORDER BY data_date")]
    px = defaultdict(dict)
    codes = defaultdict(list)
    sql = """SELECT s.data_date,r.security_code,r.payload_json
             FROM shared_datasets s JOIN shared_records r ON r.dataset_id=s.id
             WHERE s.dataset_type='px' ORDER BY s.data_date,r.security_code"""
    import json
    for day, code, raw in con.execute(sql):
        row = json.loads(raw)
        px[day][code] = row
        codes[code].append((day, row))

    days_dates = [r[0] for r in con.execute("SELECT data_date FROM shared_datasets WHERE dataset_type='days' ORDER BY data_date")]
    holder = defaultdict(dict)
    for day, code, raw in con.execute("""SELECT s.data_date,r.security_code,r.payload_json
        FROM shared_datasets s JOIN shared_records r ON r.dataset_id=s.id
        WHERE s.dataset_type='days' ORDER BY s.data_date,r.security_code"""):
        rows = json.loads(raw)
        holder[day][code] = sum((float(x[3] or 0) - float(x[2] or 0)) for x in rows)

    tipe = defaultdict(dict)
    for day, code, raw in con.execute("""SELECT s.data_date,r.security_code,r.payload_json
        FROM shared_datasets s JOIN shared_records r ON r.dataset_id=s.id
        WHERE s.dataset_type='tipe' ORDER BY s.data_date,r.security_code"""):
        row = json.loads(raw)
        tipe[day][code] = float(row[0] or 0) if row else 0.0
    con.close()
    return dates, px, codes, days_dates, holder, tipe


def safe_log_ratio(a, b):
    if a <= 0 or b <= 0:
        return 0.0
    return float(np.clip(np.log(a / b), -5, 5))


def getv(row, index, default=0.0):
    return float(row[index] or default) if len(row) > index else float(default)


def build_samples(dates, px, codes, days_dates, holder, tipe):
    rows = []
    code_index = {code: {d: i for i, (d, _) in enumerate(hist)} for code, hist in codes.items()}
    for i in range(20, len(dates) - 1):
        signal_day, target_day = dates[i], dates[i + 1]
        target_bars = px[target_day]
        prior_holder_dates = [d for d in days_dates if d < signal_day]
        holder_window = prior_holder_dates[-5:]
        prior_tipe_dates = [d for d in tipe if d < signal_day]
        tipe_day = prior_tipe_dates[-1] if prior_tipe_dates else None

        for code, cur in px[signal_day].items():
            future = target_bars.get(code)
            if not future:
                continue
            hist = codes[code]
            # The code series is sorted by date; select only data through signal close.
            end = code_index[code].get(signal_day)
            if end is None or end < 20:
                continue
            bars = [x[1] for x in hist[end - 20:end + 1]]
            close, prev_close = getv(cur, 0), getv(cur, 1)
            value, volume = getv(cur, 3), getv(cur, 2)
            avg_value = float(np.mean([getv(x, 3) for x in bars[-20:]]))
            if close <= 0 or prev_close <= 0 or value <= 0 or volume <= 0 or avg_value < MIN_AVG_VALUE:
                continue
            close5 = getv(bars[-6], 0)
            close20 = getv(bars[0], 0)
            if close5 <= 0 or close20 <= 0:
                continue
            high, low = getv(cur, 8, close), getv(cur, 9, close)
            close_position = (close - low) / (high - low) if high > low else 0.5
            prior_values = [getv(x, 3) for x in bars[:-1] if getv(x, 3) > 0]
            prior_volumes = [getv(x, 2) for x in bars[:-1] if getv(x, 2) > 0]
            mean_value = float(np.mean(prior_values[-20:])) if prior_values else value
            mean_volume = float(np.mean(prior_volumes[-20:])) if prior_volumes else volume

            tail = hist[max(0, end - 4):end + 1]
            foreign_value = sum((getv(b, 5) - getv(b, 6)) * getv(b, 0) for _, b in tail)
            traded_value = sum(getv(b, 3) for _, b in tail)
            foreign_ratio = foreign_value / traded_value if traded_value > 0 else 0.0
            bid_imbalances = []
            for _, b in tail:
                offer, bid = getv(b, 12), getv(b, 14)
                bid_imbalances.append((bid - offer) / (bid + offer) if bid + offer else 0.0)
            bid_imbalance = float(np.mean(bid_imbalances)) if bid_imbalances else 0.0

            holder_feature = None
            if len(holder_window) == 5 and tipe_day:
                shares = tipe[tipe_day].get(code, 0.0)
                if shares > 0:
                    net = sum(holder[d].get(code, 0.0) for d in holder_window)
                    holder_feature = float(np.clip(net / shares * 100.0, -5, 5))

            target_close, target_prev = getv(future, 0), getv(future, 1)
            open_target = getv(future, 7, target_prev or target_close)
            if target_close <= 0 or target_prev <= 0 or open_target <= 0:
                continue
            # Rank only the move available after the next session opens.
            # Daily OHLC cannot prove an executable opening fill.
            top_return = target_close / open_target - 1.0
            record = {
                "signal_date": signal_day, "target_date": target_day, "code": code,
                "ret_1d": close / prev_close - 1.0,
                "ret_5d": close / close5 - 1.0,
                "ret_20d": close / close20 - 1.0,
                "log_value_ratio": safe_log_ratio(value, mean_value),
                "log_volume_ratio": safe_log_ratio(volume, mean_volume),
                "close_position": close_position,
                "foreign_net_value_ratio_5d": float(np.clip(foreign_ratio, -2, 2)),
                "bid_imbalance_5d": bid_imbalance,
                "holder_net_shares_pct_5d": holder_feature,
                "label_return_open_close": top_return,
                "return_open_close_1d": target_close / open_target - 1.0,
                "return_open_close_3d": None,
                "return_open_close_5d": None,
                "avg_value20": avg_value,
            }
            for horizon, field in ((3, "return_open_close_3d"), (5, "return_open_close_5d")):
                exit_i = i + horizon
                if exit_i < len(dates):
                    exit_bar = px[dates[exit_i]].get(code)
                    if exit_bar and getv(exit_bar, 0) > 0:
                        record[field] = getv(exit_bar, 0) / open_target - 1.0
            rows.append(record)

    # Define top gainer per target session as the top fifth of positive returns.
    by_day = defaultdict(list)
    for row in rows:
        by_day[row["target_date"]].append(row)
    for day_rows in by_day.values():
        positive = [r["label_return_open_close"] for r in day_rows if r["label_return_open_close"] > 0]
        if positive:
            cutoff = float(np.quantile(positive, 1.0 - TOP_GAINER_SHARE))
            for r in day_rows:
                r["top_gainer"] = int(r["label_return_open_close"] > 0 and r["label_return_open_close"] >= cutoff)
        else:
            for r in day_rows:
                r["top_gainer"] = 0
    return rows


def fit_logit(train, feature_names, ridge=0.5, max_iter=30):
    # A deterministic stratified cap keeps repeated walk-forward fits fast while
    # retaining positives from each part of the training history.
    if len(train) > 40000:
        rng = np.random.default_rng(20261112)
        pos = [r for r in train if r["top_gainer"]]
        neg = [r for r in train if not r["top_gainer"]]
        n_pos = min(len(pos), 8000)
        n_neg = 40000 - n_pos
        pos = [pos[i] for i in sorted(rng.choice(len(pos), n_pos, replace=False))]
        neg = [neg[i] for i in sorted(rng.choice(len(neg), min(len(neg), n_neg), replace=False))]
        train = pos + neg
    X = np.asarray([[float(r[f]) for f in feature_names] for r in train], dtype=float)
    y = np.asarray([r["top_gainer"] for r in train], dtype=float)
    mean, scale = X.mean(axis=0), X.std(axis=0)
    scale[scale < 1e-9] = 1.0
    Z = np.column_stack([np.ones(len(X)), (X - mean) / scale])
    beta = np.zeros(Z.shape[1])
    penalty = np.eye(Z.shape[1]) * ridge
    penalty[0, 0] = 0.0
    for _ in range(min(max_iter, 12)):
        logits = np.clip(Z @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-logits))
        grad = Z.T @ (p - y) / len(y) + penalty @ beta / len(y)
        weights = p * (1.0 - p)
        hess = (Z.T * weights) @ Z / len(y) + penalty / len(y)
        step = np.linalg.solve(hess + np.eye(hess.shape[0]) * 1e-8, grad)
        beta -= step
        if np.linalg.norm(step) < 1e-6:
            break
    return {"mean": mean, "scale": scale, "beta": beta, "features": feature_names}


def predict(model, rows):
    X = np.asarray([[float(r[f]) for f in model["features"]] for r in rows], dtype=float)
    Z = np.column_stack([np.ones(len(X)), (X - model["mean"]) / model["scale"]])
    logits = np.clip(Z @ model["beta"], -30, 30)
    return 1.0 / (1.0 + np.exp(-logits))


def net_return(x):
    return (1.0 + x) * (1.0 - FEE_PER_SIDE) ** 2 - 1.0


def summarize(model_name, fold_name, rows, score_key, fraction):
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["target_date"]].append(r)
    selected, total_labels, total_rows = [], 0, 0
    for day_rows in by_day.values():
        ranked = sorted(day_rows, key=lambda r: r[score_key], reverse=True)
        k = max(1, int(math.ceil(len(ranked) * fraction)))
        selected.extend(ranked[:k])
        total_labels += sum(r["top_gainer"] for r in day_rows)
        total_rows += len(day_rows)
    n = len(selected)
    hits = sum(r["top_gainer"] for r in selected)
    def avg(field):
        vals = [net_return(r[field]) for r in selected if r[field] is not None]
        return float(np.mean(vals)) if vals else None
    return {
        "model": model_name, "fold": fold_name,
        "test_start": min(r["target_date"] for r in rows), "test_end": max(r["target_date"] for r in rows),
        "test_sessions": len(by_day), "eligible_rows": total_rows,
        "signals": n, "signals_per_session": n / max(len(by_day), 1),
        "selection_pct": fraction * 100,
        "base_top_gainer_rate_pct": 100.0 * total_labels / max(total_rows, 1),
        "precision_top_gainer_pct": 100.0 * hits / max(n, 1),
        "recall_top_gainer_pct": 100.0 * hits / max(total_labels, 1),
        "win_rate_net_1d_pct": 100.0 * sum(net_return(r["return_open_close_1d"]) > 0 for r in selected) / max(n, 1),
        "avg_net_return_1d_pct": 100.0 * avg("return_open_close_1d") if avg("return_open_close_1d") is not None else None,
        "avg_net_return_3d_pct": 100.0 * avg("return_open_close_3d") if avg("return_open_close_3d") is not None else None,
        "avg_net_return_5d_pct": 100.0 * avg("return_open_close_5d") if avg("return_open_close_5d") is not None else None,
    }, selected


def main():
    dates, px, codes, days_dates, holder, tipe = read_db()
    print(f"Loaded SQLite: {len(dates)} price sessions, {sum(len(v) for v in px.values())} price rows; {len(days_dates)} holder-flow dates", flush=True)
    rows = build_samples(dates, px, codes, days_dates, holder, tipe)
    print(f"Built {len(rows)} next-session samples", flush=True)
    target_dates = sorted({r["target_date"] for r in rows})
    cut1, cut2 = int(len(target_dates) * .60), int(len(target_dates) * .80)
    fold_ranges = [
        ("walk1", set(target_dates[cut1:cut2]), set(target_dates[:cut1])),
        ("walk2_oos", set(target_dates[cut2:]), set(target_dates[:cut2])),
    ]
    summaries, coefficients, selected_rows = [], [], []
    model_sets = [
        ("technical", TECH, False),
        ("market_flow", MARKET, False),
        ("market_flow_holder_subset", MARKET, True),
        ("with_holder_flow", FULL, True),
    ]
    for fold, test_dates, train_dates in fold_ranges:
        for model_name, features, require_holder in model_sets:
            train = [r for r in rows if r["target_date"] in train_dates and (not require_holder or r["holder_net_shares_pct_5d"] is not None)]
            test = [r for r in rows if r["target_date"] in test_dates and (not require_holder or r["holder_net_shares_pct_5d"] is not None)]
            if len(train) < 1000 or not test:
                continue
            print(f"Fit {fold}/{model_name}: train={len(train)} test={len(test)}", flush=True)
            model = fit_logit(train, features)
            scores = predict(model, test)
            for row, score in zip(test, scores):
                row[f"score_{fold}_{model_name}"] = float(score)
            for frac in (.05, .10, .20):
                s, chosen = summarize(model_name, fold, test, f"score_{fold}_{model_name}", frac)
                summaries.append(s)
                if frac == .10:
                    for r in chosen:
                        selected_rows.append({"model": model_name, "fold": fold, "selection_pct": 10,
                                              "signal_date": r["signal_date"], "target_date": r["target_date"],
                                              "code": r["code"], "score": r[f"score_{fold}_{model_name}"],
                                              "top_gainer": r["top_gainer"], "quality_return_open_close_pct": 100*r["label_return_open_close"],
                                              "net_return_1d_pct": 100*net_return(r["return_open_close_1d"]),
                                              "net_return_3d_pct": 100*net_return(r["return_open_close_3d"]) if r["return_open_close_3d"] is not None else None,
                                              "net_return_5d_pct": 100*net_return(r["return_open_close_5d"]) if r["return_open_close_5d"] is not None else None,
                                              "avg_value20": r["avg_value20"]})
            # Momentum baseline on exactly the same test universe.
            if model_name == "technical":
                for frac in (.05, .10, .20):
                    s, _ = summarize("momentum_5d_baseline", fold, test, "ret_5d", frac)
                    summaries.append(s)
            raw_beta = model["beta"][1:] / model["scale"]
            raw_intercept = model["beta"][0] - float(np.sum(model["beta"][1:] * model["mean"] / model["scale"]))
            coefficients.append({"fold": fold, "model": model_name, "feature": "INTERCEPT", "coefficient": raw_intercept})
            coefficients.extend({"fold": fold, "model": model_name, "feature": f, "coefficient": float(b)}
                                for f, b in zip(features, raw_beta))

    OUT.mkdir(parents=True, exist_ok=True)
    def write(name, data):
        if not data:
            return
        with (OUT / name).open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
    write("top_gainer_walk_forward_summary.csv", summaries)
    write("top_gainer_walk_forward_coefficients.csv", coefficients)
    write("top_gainer_walk_forward_top10_signals.csv", selected_rows)
    daily_holder_days = sum(1 for d in days_dates)
    print(f"DB dates: {dates[0]} to {dates[-1]} ({len(dates)} px sessions); px records={sum(len(v) for v in px.values())}; days records={sum(len(v) for v in holder.values())}; holder-flow dates={daily_holder_days}")
    print(f"Eligible next-session samples={len(rows)}; signal dates={len(target_dates)}; avg rows/session={len(rows)/max(1,len(target_dates)):.0f}; avg top-gainer base rate={100*np.mean([r['top_gainer'] for r in rows]):.2f}%")
    for s in summaries:
        print("{model:30s} {fold:12s} pick={selection_pct:4.0f}% signals={signals:6d} n/day={signals_per_session:5.1f} top-gainer precision={precision_top_gainer_pct:5.1f}% base={base_top_gainer_rate_pct:4.1f}% net1d={avg_net_return_1d_pct:7.3f}% net3d={avg_net_return_3d_pct:7.3f}% net5d={avg_net_return_5d_pct:7.3f}%".format(**{k:(v if v is not None else float('nan')) for k,v in s.items()}))
    print("Outputs:", *(str(OUT / x) for x in ["top_gainer_walk_forward_summary.csv", "top_gainer_walk_forward_coefficients.csv", "top_gainer_walk_forward_top10_signals.csv"]))


if __name__ == "__main__":
    main()
