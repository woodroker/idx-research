"""Regresi: Mean Reversion tidak wajib OTE tetapi tetap wajib bias AMD bullish."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import telegram


def ok(value, message):
    if not value:
        raise AssertionError(message)
    print("OK:", message)


# Fixture AMD daily proxy: Monday range Q1, Tuesday sweep/reclaim Q2, Wednesday bullish MSS Q3.
start = date(2026, 9, 1)
bars = []
price = 120.0
for i in range(38):
    d = start + timedelta(days=i)
    if d.weekday() >= 5:
        continue
    open_ = price
    close = price + (0.4 if i % 3 else -0.2)
    bars.append({"date": d.isoformat(), "open": open_, "high": max(open_, close) + 1.0,
                 "low": min(open_, close) - 1.0, "close": close, "volume": 100000})
    price = close
for d, open_, high, low, close, volume in [
    ("2026-11-09", 105, 108, 100, 106, 120000),
    ("2026-11-10", 105, 106, 97, 101, 200000),
    ("2026-11-11", 101, 109, 100.5, 108, 260000),
]:
    bars.append({"date": d, "open": open_, "high": high, "low": low,
                 "close": close, "volume": volume})
bars = list({x["date"]: x for x in bars}.values())
bars.sort(key=lambda x: x["date"])
ctx = telegram._amd_buy_context(bars)
ok(ctx.get("phase_bullish"), "bias AMD D/X mengarah bullish")

original_raw = telegram._scan_raw
original_amd = telegram._amd_buy_context
try:
    # Simulasikan output MR yang memang tidak memiliki status sentuh OTE.
    telegram._scan_raw = lambda code, cs, metadata=None, cfg=None: [{
        "code": code, "kind": "mr_oversold", "price": 100.0, "stop": 95.0,
        "t1": 108.0, "t2": 115.0, "score": 3.5, "date": cs[-1]["date"], "ote": None,
    }]
    cfg = dict(telegram.DEFAULTS)
    cfg["require_ote"] = True
    result = telegram.scan("TEST", bars, cfg)
    ok(any(x["kind"] == "mr_oversold" and x.get("ote") is None for x in result),
       "MR tidak diblokir mode require_ote ketika entry mean reversion valid")

    # Mode require_ote tetap berlaku untuk strategi biasa yang memang berbasis OTE.
    telegram._scan_raw = lambda code, cs, metadata=None, cfg=None: [{
        "code": code, "kind": "trend_pullback", "price": 100.0, "stop": 95.0,
        "t1": 108.0, "t2": 115.0, "score": 4.0, "date": cs[-1]["date"], "ote": None,
    }]
    result = telegram.scan("TEST", bars, cfg)
    ok(not result, "require_ote tetap menyaring strategi trend yang tidak menyentuh OTE")

    # Keputusan akhir tetap menolak MR bila konteks AMD tidak bullish.
    telegram._scan_raw = lambda code, cs, metadata=None, cfg=None: [{
        "code": code, "kind": "mr_oversold", "price": 100.0, "stop": 95.0,
        "t1": 108.0, "t2": 115.0, "score": 3.5, "date": cs[-1]["date"], "ote": None,
    }]
    _, rejected = telegram.decision({"code": "TEST", "kind": "mr_oversold", "score": 4.0,
                                     "amd_phase_bullish": False, "ax": False}, cfg)
    _, accepted = telegram.decision({"code": "TEST", "kind": "mr_oversold", "score": 4.0,
                                     "amd_phase_bullish": True, "ax": True}, cfg)
    ok(not rejected and accepted, "keputusan MR hanya lolos bila bias bullish dan konteks AMD tervalidasi")
finally:
    telegram._scan_raw = original_raw
    telegram._amd_buy_context = original_amd

print("SEMUA UJI MEAN REVERSION LULUS")
