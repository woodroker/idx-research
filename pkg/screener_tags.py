"""Tag teknikal untuk filter BUY/SELL, dihitung dari candle yang sama dengan dashboard.

Tag yang disediakan: divergence, mss, potensi_breakout, potensi_ara, potensi_ara_early, potensi_ara_momentum, four_horsemen, mean_reversion, strong_bullish.
Modul ini tidak mengirim notifikasi dan tidak mengubah keputusan/skor screener.
"""
from __future__ import annotations

import math
from typing import Any


def _atr(bars: list[dict[str, float]]) -> list[float]:
    out: list[float] = []
    total = 0.0
    for i, b in enumerate(bars):
        tr = (max(b["h"] - b["l"], abs(b["h"] - bars[i - 1]["c"]), abs(b["l"] - bars[i - 1]["c"]))
              if i else b["h"] - b["l"])
        if i < 14:
            total += tr
            out.append(total / (i + 1))
        else:
            out.append((out[i - 1] * 13 + tr) / 14)
    return out


def _pivots(bars: list[dict[str, float]], atr: list[float]) -> list[dict[str, Any]]:
    n = len(bars)
    pivots: list[dict[str, Any]] = []
    if n < 3:
        return pivots
    direction = 0
    high_price, high_i = bars[0]["h"], 0
    low_price, low_i = bars[0]["l"], 0
    for i in range(1, n):
        threshold = max(1.5 * atr[i], 0.01 * bars[i]["c"])
        if direction == 0:
            if bars[i]["h"] > high_price:
                high_price, high_i = bars[i]["h"], i
            if bars[i]["l"] < low_price:
                low_price, low_i = bars[i]["l"], i
            if high_i > low_i and high_price - low_price >= threshold:
                pivots.append({"i": low_i, "p": low_price, "t": "L"})
                direction = 1
            elif low_i > high_i and high_price - low_price >= threshold:
                pivots.append({"i": high_i, "p": high_price, "t": "H"})
                direction = -1
        elif direction == 1:
            if bars[i]["h"] >= high_price:
                high_price, high_i = bars[i]["h"], i
            elif high_price - bars[i]["l"] >= threshold:
                pivots.append({"i": high_i, "p": high_price, "t": "H"})
                direction = -1
                low_price, low_i = bars[i]["l"], i
        else:
            if bars[i]["l"] <= low_price:
                low_price, low_i = bars[i]["l"], i
            elif bars[i]["h"] - low_price >= threshold:
                pivots.append({"i": low_i, "p": low_price, "t": "L"})
                direction = 1
                high_price, high_i = bars[i]["h"], i
    if direction == 1:
        pivots.append({"i": high_i, "p": high_price, "t": "H", "prov": True})
    elif direction == -1:
        pivots.append({"i": low_i, "p": low_price, "t": "L", "prov": True})
    return pivots


def _rsi(bars: list[dict[str, float]]) -> list[float | None]:
    n = len(bars)
    period = min(14, n - 1)
    result: list[float | None] = [None] * n
    if n < 8:
        return result
    gain = loss = 0.0
    for i in range(1, period + 1):
        change = bars[i]["c"] - bars[i - 1]["c"]
        gain += max(change, 0.0)
        loss += max(-change, 0.0)
    gain /= period
    loss /= period
    result[period] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    for i in range(period + 1, n):
        change = bars[i]["c"] - bars[i - 1]["c"]
        gain = (gain * (period - 1) + max(change, 0.0)) / period
        loss = (loss * (period - 1) + max(-change, 0.0)) / period
        result[i] = 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)
    return result


def _ema(values: list[float], period: int) -> list[float | None]:
    if len(values) < period:
        return [None] * len(values)
    k = 2 / (period + 1)
    value = sum(values[:period]) / period
    out: list[float | None] = [None] * (period - 1) + [value]
    for x in values[period:]:
        value = x * k + value * (1 - k)
        out.append(value)
    return out


def _trend_score(bars: list[dict[str, float]], pivots: list[dict[str, Any]], atr: list[float]) -> int:
    highs = [p for p in pivots if p["t"] == "H"][-2:]
    lows = [p for p in pivots if p["t"] == "L"][-2:]
    structure = 0
    if len(highs) == 2 and len(lows) == 2:
        hh, hl = highs[1]["p"] > highs[0]["p"], lows[1]["p"] > lows[0]["p"]
        if hh and hl:
            structure = 1
        elif not hh and not hl:
            structure = -1
    k = min(len(bars), 20)
    values = [b["c"] for b in bars[-k:]]
    mx = (k - 1) / 2
    my = sum(values) / k
    numerator = sum((j - mx) * (v - my) for j, v in enumerate(values))
    denominator = sum((j - mx) ** 2 for j in range(k))
    movement = numerator / denominator * (k - 1) / (atr[-1] or 1) if denominator else 0
    regression = 1 if movement > 1.5 else -1 if movement < -1.5 else 0
    if structure and (regression == structure or not regression):
        return structure
    if not structure:
        return regression
    return regression if abs(movement) >= 3 else 0


def _divergence(bars: list[dict[str, float]]) -> bool:
    n = len(bars)
    if n < 10:
        return False
    atr = _atr(bars)
    pivots = _pivots(bars, atr)
    rsi = _rsi(bars)
    trend = _trend_score(bars, pivots, atr)

    def local_rsi(index: int, kind: str) -> float | None:
        vals = [rsi[j] for j in range(max(0, index - 1), min(n, index + 2)) if rsi[j] is not None]
        if not vals:
            return None
        return max(vals) if kind == "H" else min(vals)

    for kind in ("H", "L"):
        selected = [p for p in pivots if p["t"] == kind and local_rsi(p["i"], kind) is not None]
        for m in range(1, len(selected)):
            p1, p2 = selected[m - 1], selected[m]
            gap = p2["i"] - p1["i"]
            if gap < 3 or gap > 45:
                continue
            r1, r2 = local_rsi(p1["i"], kind), local_rsi(p2["i"], kind)
            if r1 is None or r2 is None:
                continue
            scale = atr[p2["i"]] or 1
            delta = p2["p"] - p1["p"]
            detected = False
            if kind == "H":
                detected = ((delta > 0.2 * scale and r2 < r1 - 3 and r1 >= 50)
                            or (delta < -0.2 * scale and r2 > r1 + 3 and trend <= 0))
            else:
                detected = ((delta < -0.2 * scale and r2 > r1 + 3 and r1 <= 50)
                            or (delta > 0.2 * scale and r2 < r1 - 3 and trend >= 0))
            if not detected:
                continue
            valid = True
            for j in range(p1["i"] + 1, p2["i"]):
                fraction = (j - p1["i"]) / gap
                price_line = p1["p"] + (p2["p"] - p1["p"]) * fraction
                rsi_line = r1 + (r2 - r1) * fraction
                if kind == "H":
                    if bars[j]["c"] > price_line + 0.1 * scale or (rsi[j] is not None and rsi[j] > rsi_line + 1.5):
                        valid = False
                        break
                elif bars[j]["c"] < price_line - 0.1 * scale or (rsi[j] is not None and rsi[j] < rsi_line - 1.5):
                    valid = False
                    break
            if valid and p2["i"] >= n - 21:
                return True
    return False


def _mss(bars: list[dict[str, float]]) -> bool:
    if len(bars) < 10:
        return False
    atr = _atr(bars)
    pivots = [p for p in _pivots(bars, atr) if not p.get("prov")]
    highs = [p for p in pivots if p["t"] == "H"][-2:]
    lows = [p for p in pivots if p["t"] == "L"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return False
    close = [b["c"] for b in bars]
    def recent_break(level: float, start: int, up: bool) -> bool:
        for j in range(start + 1, len(close)):
            crossed = close[j] > level if up else close[j] < level
            if crossed:
                return j >= len(close) - 3
        return False
    if highs[1]["p"] < highs[0]["p"] and lows[1]["p"] < lows[0]["p"]:
        return recent_break(highs[1]["p"], highs[1]["i"], True)
    if highs[1]["p"] > highs[0]["p"] and lows[1]["p"] > lows[0]["p"]:
        return recent_break(lows[1]["p"], lows[1]["i"], False)
    return False


def _potential_breakout(bars: list[dict[str, float]]) -> bool:
    n = len(bars)
    if n < 10:
        return False
    atr = _atr(bars)
    close = bars[-1]["c"]
    k = min(20, n - 1)
    previous = bars[n - 1 - k:n - 1]
    resistance = max(b["h"] for b in previous)
    tolerance = max(0.015 * close, 0.5 * atr[-1])
    if close > resistance:
        return False
    # Paritas dengan TGX() di dashboard: potensi breakout cukup dekat resistance
    # (<= 1,5% atau 0,5 ATR); tidak menambah syarat EMA yang tidak ada di UI.
    if close < resistance - tolerance:
        return False
    return True


def _four_horsemen_rules(bars: list[dict[str, float]]) -> list[str]:
    """Return both independent bullish Four Horsemen rules that match the latest bar."""
    if len(bars) < 4 or any(not b.get("ohlc_complete", True) for b in bars[-4:]):
        return []
    run = bars[-4:]
    first, second, third, fourth = run
    matched = []
    if (first["c"] < first["o"] and second["c"] > second["o"]
            and third["c"] > third["o"] and fourth["c"] > fourth["o"]
            and fourth["l"] > second["h"]
            and second["h"] < first["h"] < fourth["l"]):
        matched.append("4-bar FVG bullish")

    # The community rule uses four green bars, close above a rising EMA20.
    # Higher closes are descriptive, not an extra gate in the supplied definition.
    if len(bars) >= 21:
        closes = [b["c"] for b in bars]
        emas = _ema(closes, 20)
        ema_now, ema_prev = emas[-1], emas[-2]
        if (all(b["c"] > b["o"] for b in run) and ema_now is not None and ema_prev is not None
                and fourth["c"] > ema_now and ema_now > ema_prev):
            matched.append("4 candle hijau di atas EMA20 menanjak")
    return matched


def _four_horsemen(bars: list[dict[str, float]]) -> bool:
    """True if either or both of the configured bullish Four Horsemen rules match."""
    return bool(_four_horsemen_rules(bars))


def make_bars(raw: dict[str, Any], code: str) -> list[dict[str, float]]:
    bars: list[dict[str, float]] = []
    for day in sorted(raw.get("px", {})):
        row = (raw.get("px", {}).get(day) or {}).get(code)
        if not isinstance(row, list) or len(row) < 3:
            continue
        try:
            close = float(row[0] or 0)
            previous = float(row[1] or close)
            volume = float(row[2] or 0)
            if close <= 0:
                continue
            open_raw = float(row[7] or 0) if len(row) > 7 else 0.0
            high_raw = float(row[8] or 0) if len(row) > 8 else 0.0
            low_raw = float(row[9] or 0) if len(row) > 9 else 0.0
            open_ = open_raw if open_raw > 0 else previous or close
            high = high_raw if high_raw > 0 else close
            low = low_raw if low_raw > 0 else close
            ohlc_complete = (min(open_raw, high_raw, low_raw) > 0
                             and high_raw >= max(open_raw, close)
                             and low_raw <= min(open_raw, close))
            bars.append({"date": day, "o": open_, "h": max(high, open_, close),
                         "l": min(low, open_, close), "c": close, "v": volume,
                         "ohlc_complete": ohlc_complete})
        except (TypeError, ValueError, OverflowError):
            continue
    return bars


MR_KINDS = ("mr_oversold", "mr_bb_reclaim", "mr_capitulation")
STRONG_BULLISH_KINDS = ("bullish", "momentum")


def compute_tags(raw: dict[str, Any], metadata_by_code: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """Kembalikan tag teknikal, skor Top Gainer, dan detail skor ARA."""
    from telegram import _scan_raw
    from top_gainer import compute_scores

    top_scores = compute_scores(raw, metadata_by_code)

    tags: dict[str, list[str]] = {"divergence": [], "mss": [], "potensi_breakout": [],
                                   "potensi_ara": [], "potensi_ara_early": [], "potensi_ara_momentum": [],
                                   "four_horsemen": [], "four_horsemen_rules": {}, "mean_reversion": [], "strong_bullish": [],
                                   "potensi_top_gainer": [], "top_gainer_scores": top_scores, "ara_scores": {}}
    latest = raw.get("px", {})
    dates = sorted(latest)
    codes = set((latest.get(dates[-1]) or {}).keys()) if dates else set()
    for code in sorted(codes):
        bars = make_bars(raw, code)
        matched_rules = _four_horsemen_rules(bars)
        if matched_rules:
            tags["four_horsemen"].append(code)
            tags["four_horsemen_rules"][code] = matched_rules
        if len(bars) < 10:
            continue
        if _divergence(bars):
            tags["divergence"].append(code)
        if _mss(bars):
            tags["mss"].append(code)
        if _potential_breakout(bars):
            tags["potensi_breakout"].append(code)
        if len(bars) >= 25:
            scan_bars = [{"date": b["date"], "open": b["o"], "high": b["h"], "low": b["l"],
                          "close": b["c"], "volume": b["v"]} for b in bars]
            try:
                latest_row = (latest.get(dates[-1]) or {}).get(code) or []
                meta = dict((metadata_by_code or {}).get(code) or {})
                meta.setdefault("tradeable_shares", latest_row[15] if len(latest_row) > 15 else 0)
                scan_items = _scan_raw(code, scan_bars, metadata=meta)
                kinds = {x.get("kind") for x in scan_items}
                ara_items = [x for x in scan_items if x.get("kind") in ("ara_early", "ara_breakout")]
                if ara_items:
                    item = max(ara_items, key=lambda x: float(x.get("ara_score") or 0))
                    tags["ara_scores"][code] = {
                        "score": item.get("ara_score"), "kind": item.get("kind"),
                        "stage": item.get("ara_stage"), "date": item.get("date"),
                        "ara_price": item.get("ara_price"), "reasons": item.get("ara_reasons") or [],
                        "foreign_flow_ratio_5d": item.get("foreign_flow_ratio_5d"),
                        "foreign_flow_coverage_days": item.get("foreign_flow_coverage_days"),
                        "foreign_flow_asof": item.get("foreign_flow_asof"),
                    }
                # Pisahkan kandidat pra-breakout dari momentum ARA yang sudah bergerak.
                # Keduanya harus berasal dari _scan_raw agar lolos hard gate/score ARA.
                if "ara_early" in kinds:
                    tags["potensi_ara_early"].append(code)
                if kinds.intersection({"ara_breakout", "ara_potensi", "ara_lanjut"}):
                    tags["potensi_ara_momentum"].append(code)
                if kinds.intersection(MR_KINDS):
                    tags["mean_reversion"].append(code)
                if kinds.intersection(STRONG_BULLISH_KINDS):
                    tags["strong_bullish"].append(code)
            except Exception:
                continue
    tags["potensi_ara"] = sorted(set(tags["potensi_ara_early"]) | set(tags["potensi_ara_momentum"]))
    tags["potensi_top_gainer"] = sorted(
        (code for code, score in top_scores.items() if score.get("candidate")),
        key=lambda code: top_scores[code]["rank"],
    )
    return tags
