"""Uji outbox Telegram persisten dengan HTTP palsu (tanpa internet/kirim pesan).
Jalankan: python tools/test_telegram.py
"""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
import live
import telegram
import local_env


tmp = Path(tempfile.mkdtemp(prefix="screener-telegram-test-"))
local_env.ENV_PATH = tmp / "missing.env"  # Keep real local credentials out of this offline test.
database.DB_PATH = tmp / "test.db"
database.initialize()
telegram.CFG_PATH = tmp / "telegram.json"
telegram.SIG_PATH = tmp / "signals_today.json"
telegram.HIST_PATH = tmp / "signals_history.json"
telegram._today = lambda: "2026-11-06"
live.market_open = lambda now=None: True
telegram.quality_line = lambda code: "13,0/14 - Undervalued"
sleeps, sent = [], []
real_time = time
telegram.time = types.SimpleNamespace(sleep=lambda seconds: sleeps.append(seconds), time=real_time.time)
mode = {"value": "ok"}


def fake_http(token, method, payload, timeout=10):
    if mode["value"] == "ok":
        sent.append(payload["text"])
        return 200, {"ok": True}
    if mode["value"] == "429":
        mode["value"] = "ok"
        return 429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}}
    if mode["value"] == "401":
        return 401, {"ok": False, "description": "Unauthorized"}
    return 500, {"ok": False, "description": "Server error"}


telegram.HTTP = fake_http


def cfg(**changes):
    base = dict(telegram.DEFAULTS)
    base.update(token="TEST_TOKEN", chat_id="12345", enabled=True, max_per_day=20, max_burst=5,
                min_gap_sec=4, per_code_per_day=1, market_only=True, live_only=True)
    base.update(changes)
    telegram.CFG_PATH.write_text(json.dumps(base), encoding="utf-8")


def item(code="BBCA", price=5200, **changes):
    row = dict(code=code, kind="ote", price=price, lo=5100, hi=5300, low=5150, high=5250,
               stop=5000, t1=5500, t2=5800, date="2026-11-06", score=4.5, dec=68.0,
               ote="sentuh", fase="Accumulation")
    row.update(changes)
    return row


def queue_counts():
    conn = database.connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM telegram_outbox WHERE status IN ('pending','processing')").fetchone()[0]
    finally:
        conn.close()


def drain(timeout=5):
    deadline = real_time.time() + timeout
    while real_time.time() < deadline:
        if queue_counts() == 0:
            return
        real_time.sleep(0.01)
    raise AssertionError("Telegram outbox belum selesai diproses")


def ok(condition, message):
    print(("OK   " if condition else "GAGAL ") + message)
    assert condition, message


# Import dan enqueue tidak boleh menyalakan thread secara implisit.
ok(telegram._sender_thread is None and telegram._scan_thread is None, "import telegram tidak memulai thread")
ok(all(telegram._kgrp(k) == "reversal" for k in ("reversal", "mr_oversold", "mr_bb_reclaim", "mr_capitulation")),
   "AMD reversal dan tiga jenis mean reversion masuk kuota REVERSAL")
cfg(enabled=False); result = telegram.enqueue([item()])
ok(result["accepted"] == 0, "notifikasi nonaktif -> tidak masuk antrean")
cfg(token=""); result = telegram.enqueue([item()])
ok(result["accepted"] == 0, "token kosong -> tidak masuk antrean")

cfg(); result = telegram.enqueue([item()])
ok(result["accepted"] == 1, "sinyal valid tersimpan ke database outbox")
legacy = telegram.enqueue([item("OLDOTE", kind="ote_gagal")])
ok(legacy["accepted"] == 0 and legacy["skipped"].get("sinyal OTE GAGAL telah dihentikan") == 1,
   "sinyal OTE GAGAL ditolak dan tidak masuk antrean")
ok(queue_counts() == 1 and telegram._sender_thread is None, "outbox persisten dan enqueue tidak memulai worker")
state = telegram.start(sender=True, scanner=False)
ok(state["sender"] and not state["scanner"], "sender dapat dijalankan eksplisit tanpa scanner")
drain()
ok(len(sent) == 1, "satu sinyal diproses worker")
msg = sent[0]
for required in ("BELI - BBCA", "OTE Buy: 5.200", "Stop: 5.000", "TP1: 5.500", "TP2: 5.800",
                 "Fase: Accumulation", "Status: Pullback - menyentuh zona OTE"):
    ok(required in msg, "format Telegram memuat " + required)

reversal = item("BBRI", kind="reversal", price=515, stop=490, t1=560, t2=610,
                 entry_lo=505, entry_hi=525, entry_source="Bullish OB Q2 (proxy harian)",
                 true_open=530, q1_high=570, amd_reasons=["Q2 sweep Low Q1 dan reclaim", "Q3/X bullish MSS"])
reversal_msg = telegram.format_message(reversal)
ok(reversal_msg.splitlines()[0].startswith("🔄 REVERSAL - BBRI"), "baris pertama reversal memakai status dan kode")
for required in ("Zona entry Bullish OB Q2", "Stop: 490", "TP1: 560", "TP2: 610"):
    ok(required in reversal_msg, "notifikasi reversal detail memuat " + required)

# Mean-reversion tetap mempertahankan sub-strategi, tetapi dikelompokkan sebagai REVERSAL.
for mr_kind, mr_name in (("mr_oversold", "oversold"), ("mr_bb_reclaim", "Bollinger"), ("mr_capitulation", "capitulation")):
    mr_item = item("MR" + str(len(mr_kind)), kind=mr_kind, price=515, stop=490, t1=560, t2=610,
                   score=4.5, amd_phase_bullish=True, fase="Distribution")
    mr_msg = telegram.format_message(mr_item)
    ok(mr_msg.splitlines()[0].startswith("🔄 REVERSAL - " + mr_item["code"]), mr_kind + " memakai header REVERSAL")
    expected_status = {"mr_oversold": "Status: Reversal - oversold memantul",
                       "mr_bb_reclaim": "Status: Reversal - kembali masuk Bollinger bawah",
                       "mr_capitulation": "Status: Reversal - capitulation + hammer"}[mr_kind]
    ok(expected_status in mr_msg, mr_kind + " mempertahankan deskripsi sub-strategi")
ara_msg = telegram.format_message(item("PRAA", kind="ara_early", ara_stage="PRE-BREAKOUT", ara_score=72,
                                         ara_price=12500, trig=10100, ara_reasons=["relative volume 1.8x"]))
ok(ara_msg.splitlines()[0].startswith("👀 PRE-ARA - PRAA"), "header Pre-ARA sejajar dan jelas")
ok("Trigger: tembus" in ara_msg and "Entry / OTE:" not in ara_msg, "pra-ARA menampilkan trigger, bukan rekomendasi entry limit")
ok("Status: Pra-breakout:" in ara_msg, "status notifikasi memakai deskripsi Pre-ARA")
ok("gagal OTE" not in ara_msg, "status gagal OTE tidak disisipkan ke notifikasi")
break_msg = telegram.format_message(item("BRKA", kind="ara_breakout", ara_stage="BREAKOUT TERKONFIRMASI",
                                          ara_score=80, ara_price=12500, trig=10100, ara_reasons=["volume konfirmasi"]))
ok(break_msg.splitlines()[0].startswith("🚀 BREAKOUT ARA - BRKA"), "header breakout ARA terkonfirmasi")
ok("Konfirmasi: close sudah di atas resistance" in break_msg, "breakout ARA menjelaskan konfirmasi resistance")

result = telegram.enqueue([item()])
ok(result["accepted"] == 0 and "sudah dinotifikasi hari ini" in result["skipped"], "sinyal terkirim tidak dikirim ulang")
ok(len(sent) == 1, "tidak ada pesan duplikat")

result = telegram.enqueue([item("A%d" % i) for i in range(8)])
ok(result["accepted"] == 5 and result["skipped"].get("batas per kiriman") == 3, "batas burst berlaku pada antrean persisten")
drain()

cfg(max_per_day=8)
result = telegram.enqueue([item("B%d" % i) for i in range(5)])
drain()
ok(telegram._count_today() <= 8, "batas harian tidak terlampaui (%s <= 8)" % telegram._count_today())

cfg()
for name, row, reason in [
    ("data bukan hari ini", item("C1", date="2026-11-05"), "data bukan hari ini"),
    ("harga di luar zona OTE", item("C2", price=5400, low=5400, high=5400), "harga belum menyentuh OTE"),
    ("level tidak valid", item("C3", stop=5300), "level stop/target tidak valid"),
    ("data tidak lengkap", {"code": "C4"}, "data tidak lengkap"),
]:
    result = telegram.enqueue([row])
    ok(result["accepted"] == 0 and reason in result["skipped"], "validasi menolak: " + name)

live.market_open = lambda now=None: False
result = telegram.enqueue([item("D1")])
ok(result["accepted"] == 0 and "bursa tutup" in result["skipped"], "bursa tutup -> tidak masuk antrean")
live.market_open = lambda now=None: True

mode["value"] = "429"; sleeps.clear()
result = telegram.enqueue([item("E1")]); drain()
ok(any(seconds >= 4 for seconds in sleeps) and any("BELI - E1" in message for message in sent), "HTTP 429 -> retry_after lalu berhasil terkirim")

mode["value"] = "401"
result = telegram.enqueue([item("F1")]); drain()
ok(telegram.STATE["blocked"] and "Unauthorized" in (telegram.STATE["last_error"] or ""), "token ditolak -> worker memblokir pengiriman")
mode["value"] = "ok"
result = telegram.enqueue([item("F2")])
ok(result["accepted"] == 0, "setelah blokir, sinyal baru tidak diantrikan")
ok(telegram.status()["sent_today"] >= 1 and "TEST_TOKEN" not in json.dumps(telegram.status()), "status tidak membocorkan token")

# Periksa outbox tetap menyimpan status terminal dan jejak percobaan.
conn = database.connect()
try:
    statuses = {row[0] for row in conn.execute("SELECT DISTINCT status FROM telegram_outbox").fetchall()}
finally:
    conn.close()
ok("sent" in statuses and "failed" in statuses, "outbox mencatat status terkirim dan gagal")

telegram.STATE["blocked"] = False
result = telegram.toggle(False)
ok(result["ok"] and json.loads(telegram.CFG_PATH.read_text())["enabled"] is False, "toggle menonaktifkan notifikasi")
telegram.stop()
print("SEMUA UJI TELEGRAM LULUS")
