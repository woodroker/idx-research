"""Hubungkan bot Telegram: kirim /start ke bot Anda dulu, lalu jalankan:  py telegram_setup.py
Mencari chat_id Anda dari pesan terakhir ke bot, menyimpannya ke telegram.json, dan mengirim pesan konfirmasi."""
import sys
import telegram

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
ok, fatal, err = telegram._send_text(telegram.load_cfg(), "Terhubung. Notifikasi OTE screener aktif.")
print("Pesan konfirmasi:", "terkirim" if ok else "gagal (%s)" % err)
