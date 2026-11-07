"""Uji notifikasi Telegram dengan HTTP palsu (tanpa internet, tanpa mengirim apa pun). Jalankan: python tools/test_telegram.py"""
import json, os, sys, tempfile, time, types
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database, live, telegram

tmp = Path(tempfile.mkdtemp())
database.DB_PATH = tmp / "t.db"; database.initialize()
telegram.CFG_PATH = tmp / "telegram.json"
sleeps, sent = [], []
telegram.time = types.SimpleNamespace(sleep=lambda s: sleeps.append(s), time=time.time)    # tanpa menunggu sungguhan; jeda tercatat
telegram._today = lambda: "2026-11-06"
live.market_open = lambda now=None: True
telegram.quality_line = lambda code: "13,0/14 - Undervalued"
mode = {"v": "ok"}
def fake_http(token, method, payload, timeout=10):
    if mode["v"] == "ok":
        sent.append(payload["text"]); return 200, {"ok": True}
    if mode["v"] == "429":
        mode["v"] = "ok"; return 429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}}
    if mode["v"] == "401":
        return 401, {"ok": False, "description": "Unauthorized"}
telegram.HTTP = fake_http
def cfg(**k):
    base = dict(token="T", chat_id="1", enabled=True, max_per_day=20, max_burst=5, min_gap_sec=4, per_code_per_day=1, market_only=True, live_only=True); base.update(k)
    telegram.CFG_PATH.write_text(json.dumps(base))
def item(code="BBCA", price=5200, **k):
    d = dict(code=code, price=price, lo=5100, hi=5300, stop=5000, t1=5500, t2=5800, date="2026-11-06"); d.update(k); return d
def drain():
    telegram.start()
    t0 = time.time()
    while (telegram.Q.qsize() or telegram._pending) and time.time() - t0 < 10: time.sleep(0.01) if hasattr(time, "sleep") else None
    t0 = time.time()
    while telegram._pending and time.time() - t0 < 5: pass
def ok(c, msg):
    print(("OK   " if c else "GAGAL ") + msg); assert c, msg

cfg(enabled=False); r = telegram.enqueue([item()]); ok(r["accepted"] == 0, "nonaktif -> tidak ada yang diterima")
cfg(token=""); r = telegram.enqueue([item()]); ok(r["accepted"] == 0, "belum dikonfigurasi -> ditolak")
cfg(); r = telegram.enqueue([item()]); drain()
ok(r["accepted"] == 1 and len(sent) == 1, "kandidat valid terkirim 1 pesan")
ok(sent[0].split("\n") == ["Emiten: BBCA", "Status: masuk area OTE - harga sekarang 5.200", "Stop: 5.000", "Target TP 1: 5.500", "Target TP 2: 5.800", "Skor kualitas: 13,0/14 - Undervalued"], "format pesan sesuai permintaan")
ok(max(sleeps) >= 4, "jeda >= 4 dtk setelah kirim (tercatat %s)" % sleeps[-1])
r = telegram.enqueue([item()]); ok(r["accepted"] == 0 and "sudah dinotifikasi hari ini" in r["skipped"], "emiten sama di hari sama tidak dikirim ulang")
ok(len(sent) == 1, "tidak ada pesan ganda")
r = telegram.enqueue([item("A%d" % i) for i in range(8)]); drain()
ok(r["accepted"] == 5 and r["skipped"].get("batas per kiriman") == 3, "burst dibatasi 5 per kiriman (3 dibuang)")
cfg(max_per_day=8); r = telegram.enqueue([item("B%d" % i) for i in range(5)]); drain()
ok(telegram._count_today() <= 8, "batas harian tidak terlampaui (terkirim %d <= 8)" % telegram._count_today())
cfg(); sent.clear()
for name, it, why in [("data bukan hari ini", item("C1", date="2026-11-05"), "data bukan hari ini"), ("harga di luar zona", item("C2", price=5400), "harga di luar zona OTE"),
                      ("level tidak valid", item("C3", stop=5300), "level stop/target tidak valid"), ("data tidak lengkap", {"code": "C4"}, "data tidak lengkap")]:
    r = telegram.enqueue([it]); ok(r["accepted"] == 0 and why in r["skipped"], "ditolak: " + name)
live.market_open = lambda now=None: False; r = telegram.enqueue([item("D1")]); ok(r["accepted"] == 0 and "bursa tutup" in r["skipped"], "bursa tutup -> tidak kirim"); live.market_open = lambda now=None: True
mode["v"] = "429"; sleeps.clear(); r = telegram.enqueue([item("E1")]); drain()
ok(any(s == 4 for s in sleeps) and sent and "E1" in sent[-1], "HTTP 429: menunggu retry_after+1 lalu terkirim")
mode["v"] = "401"; r = telegram.enqueue([item("F1")]); drain()
ok(telegram.STATE["blocked"] and "Unauthorized" in (telegram.STATE["last_error"] or ""), "token salah (401): notifikasi dimatikan otomatis")
mode["v"] = "ok"; r = telegram.enqueue([item("F2")]); ok(r["accepted"] == 0, "setelah blokir tidak mencoba lagi")
ok(telegram.status()["sent_today"] >= 1 and "token" not in json.dumps(telegram.status()), "status tidak membocorkan token")
telegram.STATE["blocked"] = False; res = telegram.toggle(False); ok(res["ok"] and json.loads(telegram.CFG_PATH.read_text())["enabled"] is False, "toggle mematikan & tersimpan")
print("SEMUA UJI TELEGRAM LULUS")
