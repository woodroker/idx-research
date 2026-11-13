"""Proses worker Telegram terpisah dari web server.

Jalankan: py telegram_worker.py            (worker pemindai + pengirim)
          py telegram_worker.py --setup    (hubungkan bot / simpan chat_id)
Environment:
  SCREENER_TELEGRAM_SCAN=1          -> aktifkan pemindaian otomatis (default 1)
  SCREENER_TELEGRAM_SCAN=0          -> hanya kirim antrean yang dibuat dashboard/API
  SCREENER_TELEGRAM_LEASE_SECONDS=45 -> masa lease worker (heartbeat tiap 10 detik)
"""
import os
import signal
import socket
import threading
import uuid
import argparse
import datetime

import database
import telegram

WIB = datetime.timezone(datetime.timedelta(hours=7))
WINDOWS = {
    "morning": (datetime.time(8, 20), datetime.time(13, 5)),
    "afternoon": (datetime.time(13, 20), datetime.time(16, 0)),
}


def setup():
    """Hubungkan bot: kirim /start ke bot dulu, lalu jalankan  py telegram_worker.py --setup
    Mencari chat_id dari pesan terakhir ke bot, menyimpannya ke telegram.json, dan mengirim pesan konfirmasi."""
    import sys

    cfg = telegram.load_cfg()
    if not cfg["token"]:
        sys.exit("Isi dulu \"token\" di telegram.json (dari @BotFather).")
    code, me = telegram.HTTP(cfg["token"], "getMe", {})
    if not me.get("ok"):
        sys.exit("Token ditolak Telegram: %s" % me.get("description", code))
    print("Bot terhubung: @%s" % me["result"].get("username"))
    code, up = telegram.HTTP(cfg["token"], "getUpdates", {"limit": 20, "timeout": 0})
    chats = {}
    for u in up.get("result", []):
        m = u.get("message") or u.get("channel_post") or {}
        if m.get("chat"):
            chats[m["chat"]["id"]] = m["chat"].get("first_name") or m["chat"].get("title") or m["chat"].get("username") or "?"
    if not chats:
        sys.exit("Belum ada pesan ke bot. Buka Telegram, cari @%s, tekan START / kirim 'hai', lalu jalankan ulang." % me["result"].get("username"))
    cid = list(chats)[-1]
    telegram.save_cfg(chat_id=str(cid), enabled=True)
    print("chat_id tersimpan: %s (%s). Notifikasi DIAKTIFKAN." % (cid, chats[cid]))
    telegram.load_cfg()
    ok, fatal, err = telegram._send_text(telegram.load_cfg(), "Terhubung. Notifikasi sinyal trading Stock Screener aktif.")
    print("Pesan konfirmasi:", "terkirim" if ok else "gagal (%s)" % err)


def main(window=None):
    if window not in (None, *WINDOWS):
        raise ValueError("window harus morning atau afternoon")
    if window:
        window_start, window_end = WINDOWS[window]
        while True:
            now = datetime.datetime.now(WIB).time()
            if now >= window_end:
                print("Jendela %s sudah berakhir; worker tidak dijalankan." % window, flush=True)
                return 0
            if now >= window_start:
                break
            time.sleep(1)
    window_end = WINDOWS[window][1] if window else None
    database.initialize()
    scanner_enabled = os.environ.get("SCREENER_TELEGRAM_SCAN", "1").strip().lower() not in ("0", "false", "no", "off")
    stopped = threading.Event()
    owner = "%s:%s:%s" % (socket.gethostname(), os.getpid(), uuid.uuid4().hex[:8])
    lease_seconds = max(30, int(os.environ.get("SCREENER_TELEGRAM_LEASE_SECONDS", "45")))

    def handle_stop(_signum, _frame):
        # Signal handler hanya meminta shutdown. Join thread dilakukan di main flow,
        # bukan di dalam handler, agar tidak memblokir penanganan sinyal.
        stopped.set()

    for sig in (getattr(signal, "SIGINT", None), getattr(signal, "SIGTERM", None),
                getattr(signal, "SIGBREAK", None)):
        if sig is not None:
            try:
                signal.signal(sig, handle_stop)
            except (ValueError, OSError):
                pass

    if not telegram.acquire_worker_lease(owner, lease_seconds):
        print("Telegram worker tidak dijalankan: worker lain masih memegang lease untuk database ini.", flush=True)
        return 2

    try:
        state = telegram.start(sender=True, scanner=scanner_enabled)
        print("Telegram worker aktif | sender=%s | scanner=%s | window=%s | database=%s" %
              (state["sender"], state["scanner"], window or "always", database.DB_PATH), flush=True)
        while not stopped.is_set():
            if window_end and datetime.datetime.now(WIB).time() >= window_end:
                print("Batas waktu worker %s WIB tercapai." % window_end.strftime("%H:%M"), flush=True)
                stopped.set()
                break
            if stopped.wait(10.0):
                break
            if not telegram.renew_worker_lease(owner, lease_seconds):
                print("Lease Telegram worker hilang; menghentikan worker untuk mencegah proses ganda.", flush=True)
                stopped.set()
    except KeyboardInterrupt:
        pass
    finally:
        remaining = telegram.stop(timeout=60)
        telegram.release_worker_lease(owner)
        if remaining and any(remaining.values()):
            raise RuntimeError("Worker Telegram belum selesai; database tidak aman untuk disinkronkan: %s" % remaining)
        print("Telegram worker berhenti.", flush=True)
    return 0


if __name__ == "__main__":
    import sys
    if "--setup" in sys.argv[1:]:
        setup()
        raise SystemExit(0)
    parser = argparse.ArgumentParser(description="Jalankan worker Telegram screener.")
    parser.add_argument("--window", choices=tuple(WINDOWS), help="Jalankan hanya pada jendela waktu cloud WIB.")
    args = parser.parse_args()
    raise SystemExit(main(window=args.window))
