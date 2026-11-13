"""Uji dasar empat tag filter teknikal tanpa akses jaringan atau Telegram."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screener_tags import compute_tags, make_bars, _potential_breakout, _mss, _divergence


def ok(condition, message):
    if not condition:
        raise AssertionError(message)
    print("OK:", message)


keys = {"divergence", "mss", "potensi_breakout", "potensi_ara", "potensi_ara_early", "potensi_ara_momentum", "mean_reversion", "strong_bullish"}
empty = compute_tags({})
ok(keys.issubset(empty) and all(not empty[k] for k in keys), "empat kategori tersedia saat database belum berisi data")

# Store price row layout: close, previous close, volume, value, ..., open, high, low.
raw = {"px": {"2026-11-%02d" % day: {"TEST": [100 + day / 10, 100 + (day - 1) / 10, 1000, 100000,
         0, 0, 0, 100, 102 + day / 10, 98 + day / 10]} for day in range(1, 27)}}
bars = make_bars(raw, "TEST")
ok(len(bars) == 26 and bars[0]["c"] > 0 and bars[-1]["h"] >= bars[-1]["c"] >= bars[-1]["l"],
   "konversi OHLCV menggunakan kolom harga yang benar")
ok(isinstance(_divergence(bars), bool), "deteksi divergence mengembalikan boolean")
ok(isinstance(_mss(bars), bool), "deteksi MSS mengembalikan boolean")
ok(isinstance(_potential_breakout(bars), bool), "deteksi potensi breakout mengembalikan boolean")
print("SEMUA UJI TAG SCREENER LULUS")
