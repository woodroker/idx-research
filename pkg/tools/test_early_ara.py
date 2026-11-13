"""Synthetic tests for early ARA detection stages. Not a performance backtest."""
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import telegram


def ok(value, message):
    if not value:
        raise AssertionError(message)
    print("OK:", message)


telegram._day_frac = lambda _day: 1.0


def history(last_close=10030, last_high=10040, last_low=9995, last_volume=180000):
    bars = []
    # 32 weekdays of synthetic prices: earlier range wider, the last five sessions contract.
    for i in range(45):
        d = date(2026, 8, 15) + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        close = 9600 + i * 8
        rg = 220 if i < 25 else 100
        bars.append({"date": d.isoformat(), "open": close - 15, "high": close + rg/2,
                     "low": close - rg/2, "close": close, "volume": 100000})
    for x in bars[-6:-1]:
        x.update(open=9990, high=10100, low=9900, close=10000, volume=100000)
    bars[-1].update(date="2026-11-10")
    bars.append({"date": "2026-11-11", "open": 10000, "high": last_high, "low": last_low,
                 "close": last_close, "volume": last_volume})
    return bars


meta = {"tradeable_shares": 50_000_000}
cfg = {"ara_min_value": 500_000_000, "ara_early_min_score100": 62,
       "ara_breakout_min_score100": 65}

pre = telegram._early_ara_candidate("PREA", history(), meta, cfg)
ok(pre is not None and pre["kind"] == "ara_early", "pra-breakout dikenali sebelum resistance pecah")
ok(pre["ara_stage"] == "PRE-BREAKOUT" and pre["score"] >= 3.0, "tahap dan skor pra-ARA tersedia")
ok(pre["stop"] < pre["price"] < pre["trig"] < pre["t2"], "level pra-ARA valid: SL < harga < trigger < ARA")

breakout = telegram._early_ara_candidate("BRKA", history(last_close=10120, last_high=10135, last_low=10080, last_volume=220000), meta, cfg)
ok(breakout is not None and breakout["kind"] == "ara_breakout", "breakout resistance menghasilkan tahap konfirmasi ARA")
ok(breakout["ara_stage"] == "BREAKOUT TERKONFIRMASI", "label tahap breakout terkonfirmasi benar")
ok(breakout["stop"] < breakout["price"] < breakout["t2"], "level breakout ARA memiliki SL dan batas ARA valid")

low_volume = telegram._early_ara_candidate("LOWV", history(last_volume=50000), meta, cfg)
ok(low_volume is None, "kandidat ditolak ketika volume relatif tidak cukup")

extended = telegram._early_ara_candidate("EXTD", history(last_close=11600, last_high=11630, last_low=11550, last_volume=300000), meta, cfg)
ok(extended is None, "harga yang sudah terlalu jauh dari batas ARA tidak dilabeli deteksi dini")

no_float = telegram._early_ara_candidate("NOFLT", history(), {}, cfg)
ok(no_float is not None, "deteksi tetap dapat berjalan tanpa data saham tradable; bobot turnover dinormalisasi")
print("SEMUA UJI DETEKSI DINI ARA LULUS (synthetic, bukan backtest)")
