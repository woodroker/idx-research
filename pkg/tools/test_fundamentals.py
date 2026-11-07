"""Uji logika skor/kuadran/sinyal fundamental dengan data tiruan (tanpa internet). Jalankan: python tools/test_fundamentals.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fundamentals as F
M = 1e6
ds = ["2026-09-30", "2026-06-30", "2026-03-31", "2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31", "2024-12-31"]
base = [(900, 150), (950, 140), (980, 120), (1000, 110), (1100, 60), (1150, 50), (1200, 45), (1250, 40)]
Q = lambda g=1.0: [{"d": d, "rev": r * M, "ni": n * M * (g if i < 4 else 1)} for i, (d, (r, n)) in enumerate(zip(ds, base))]
A = [{"d": "2025-12-31", "rev": 4200 * M, "ni": 520 * M, "eq": 3600 * M, "debt": 900 * M, "shares": 100 * M},
     {"d": "2024-12-31", "rev": 4700 * M, "ni": 195 * M, "eq": 3200 * M, "debt": 1200 * M, "shares": 100 * M},
     {"d": "2023-12-31", "rev": 4500 * M, "ni": 210 * M, "eq": 3100 * M, "debt": 1100 * M, "shares": 100 * M}]
def raw(**k):
    i = {"sector": "Basic Materials", "marketCap": 6e11, "trailingPE": 4.6, "priceToBook": .67, "returnOnEquity": .20, "profitMargins": .18}; i.update(k)
    return {"info": i, "q": Q(), "a": A, "div12": 5, "low52": 52, "high52": 150}
r = F.analyze(raw(), 101)
assert r["signal"]["action"] == "BUY" and r["quadrant"]["id"] == "I" and r["score14"]["total"] == 14, r["signal"]
assert F.analyze(raw(trailingPE=22, priceToBook=3.2), 101)["signal"]["action"] == "HOLD"            # bagus tapi mahal (Kuadran II)
trap = raw(returnOnEquity=.05, priceToBook=.6, profitMargins=.04, trailingPE=30); trap["q"] = Q(.3)
assert F.analyze(trap, 101)["signal"]["action"] == "SELL" and F.analyze(trap, 101)["quadrant"]["id"] == "III"   # value trap
assert F.analyze({}, None)["signal"]["action"] == "WAIT"                                              # data kosong tidak mengarang
assert abs(F.analyze(raw(), 101)["range52"]["pos"] - 50) < .1
assert any("dividend" in w for w in F.analyze(dict(raw(), div12=110), 101)["warnings"])               # yield 109% ditandai
fin = raw(sector="Financial Services", debtToEquity=900); fin["a"] = [dict(x, debt=x["eq"] * 9) for x in A]
sc = F.analyze(fin, 101)["score14"]; assert "DER" in sc["na"] and sc["total"] == 14                    # DER n/a utk keuangan, skor dinormalisasi
print("OK: skor 14, kuadran, sinyal BUY/HOLD/SELL/WAIT")
