"""Uji AMD daily-proxy dan reversal BUY. Tidak mengklaim validasi intraday M1/M3/M5."""
import sys
from datetime import date, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import telegram


def ok(value, message):
    if not value:
        raise AssertionError(message)
    print("OK:", message)

# Build a steady 40-bar history ending Tuesday/Wednesday in a current trading week.
# Historical candles are synthetic; last week has Q1 Monday range and Q2 Tuesday sell-side sweep.
start = date(2026, 9, 1)
bars=[]
price=120.0
for i in range(38):
    d=start+timedelta(days=i)
    if d.weekday() >= 5:
        continue
    o=price; c=price + (0.4 if i%3 else -0.2)
    bars.append({"date":d.isoformat(),"open":o,"high":max(o,c)+1.0,"low":min(o,c)-1.0,"close":c,"volume":100000})
    price=c
# Make the last completed trading week sequence explicit.
# The most recent Monday, Tuesday and Wednesday are overwritten to create AMD + MSS proxy.
last_week=[]
for j in range(len(bars)-1,-1,-1):
    if bars[j]["date"] >= (bars[-1]["date"]):
        pass
# Extend to a known Mon/Tue/Wed at the end (2026-11-09/10/11).
for d, o, h, l, c, v in [
    ("2026-11-09", 105, 108, 100, 106, 120000),
    ("2026-11-10", 105, 106, 97, 101, 200000),
    ("2026-11-11", 101, 109, 100.5, 108, 260000),
]:
    bars.append({"date":d,"open":o,"high":h,"low":l,"close":c,"volume":v})
# Remove any overlapping/duplicate earlier dates, sort chronologically.
uniq={x["date"]:x for x in bars}
bars=[uniq[k] for k in sorted(uniq)]
ctx=telegram._amd_buy_context(bars)
ok(ctx.get("swept") and ctx.get("reclaimed"), "Q2 sweep dan reclaim terdeteksi")
ok(ctx.get("valid"), "Q3 bullish close di atas high Q2 dan fase AMDX bullish lolos")
out=telegram._scan_raw("TEST", bars)
rev=[x for x in out if x["kind"]=="reversal"]
ok(len(rev)==1, "reversal BUY dihasilkan dari Q1/Q2/Q3 + OB/FVG")
if rev:
    x=rev[0]
    ok(x["stop"] < x["price"] < x["t1"] < x["t2"], "urutan stop < entry < TP1 < TP2 valid")
    ok(x["entry_lo"] < x["price"] < x["entry_hi"], "entry limit berada di zona FVG/OB")
    ok(x["entry_hi"] <= min(x["true_open"], (x["q1_high"]+x["q1_low"])/2), "zona entry berada di discount terhadap True Open/Q1 midpoint")
    detail = x["amd_score_detail"]
    expected_max = {"structure": 25, "buying_pressure": 25, "trend_momentum": 20,
                    "pullback_quality": 15, "liquidity_risk": 15}
    ok({k: detail[k]["max"] for k in expected_max} == expected_max,
       "bobot Model B tepat 25/25/20/15/15 = 100 poin")
    subtotal = sum(detail[k]["score"] for k in expected_max)
    ok(abs(subtotal - x["amd_quality_score"]) < 0.11,
       "total Quality Score sama dengan jumlah lima komponen")
    ok(abs(x["score"] * 20 - x["amd_quality_score"]) < 0.11,
       "skor 0-5 konsisten dengan skor AMD BUY 0-100")
    ok(telegram.DEFAULTS["reversal_min_score"] == 4.0,
       "ambang Model B default sementara 80/100")
print("SEMUA UJI AMD REVERSAL LULUS")
