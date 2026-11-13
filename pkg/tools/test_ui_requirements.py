"""Static regression tests for original UI requirements. ui.js is intentionally immutable."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "templates/index.html").read_text(encoding="utf-8")
app = (ROOT / "static/app.js").read_text(encoding="utf-8")
ui = ROOT / "static/ui.js"
ui_hash = hashlib.sha256(ui.read_bytes()).hexdigest()
expected_ui_hash = "8cf1371662996a47f52d28330046f3a9b63cbd63aa20fcbe03705c677d641e77"
assert ui_hash == expected_ui_hash, "static/ui.js berubah; dilarang diubah"
assert "BSM={f:'all',tags:[],q:'',lim:10" in app, "tabel Ringkasan harus mulai 10 emiten"
assert "BSM.lim+=10" in app, "Tampilkan lebih banyak Ringkasan harus menambah 10"
assert "window.__tgmore=window.__tgmore||[5,5,5,5]" in app, "Top Gainer/Loser harus mulai 5 per tab"
assert 'Tampilkan lebih banyak (+5)' in app, "Top Gainer/Loser harus punya tombol tambah 5"
assert all(f'data-bx="{x}"' in html for x in ("divergence", "mss", "potensi_breakout", "potensi_ara")), "empat filter teknikal wajib tersedia"
assert 'data-bx="amdx"' not in html and 'data-bx="phase"' not in html, "filter fase AMDX tidak boleh ada"
assert "const PCT={fvg:1,ote:1,sd:1,dv:1,ma:1,lv:1,ys:0}" in app, "overlay fase chart harus nonaktif"
assert "Muat Ulang (DB)" not in html, "tombol manual reload DB harus dihapus"
assert 'static/app.js' in html and 'static/ui.js' in html, "script aplikasi/original UI harus tetap terpasang"
print("OK: UI Original, batas 10 +10, Top Gainer +5, filter teknikal, fase chart off, ui.js utuh")

assert "Pre-ARA" in app and "PRA-ARA" not in app, "label BUY/SELL harus Pre-ARA"
assert "Pre-ARA" in html, "kartu halaman Sinyal harus memakai label Pre-ARA"
assert "PRA-ARA" not in app, "Pre-ARA tidak boleh muncul di Top Gainer"
assert "o.push([label,'#a855f7'" in app and "?'Pre-ARA " in app, "Pre-ARA harus masuk renderer BUY/SELL"

for kind in ("mr_oversold", "mr_bb_reclaim", "mr_capitulation"):
    assert f"{kind}: ['MEAN REVERSION', 'rev'" in html, f"{kind} harus diklasifikasikan sebagai REVERSAL pada halaman Sinyal"

# Top Gainer/Loser harus mendukung ekspansi di tiap tab dan tidak memakai tag Pre-ARA.
tgl = app.split('function TGL(){', 1)[1].split("$('#tg').addEventListener", 1)[0]
assert "window.__tgmore=window.__tgmore||[5,5,5,5]" in tgl, "empat tab Top Movers mulai dari 5"
assert 'all.slice(0,limit)' in tgl, "baris Top Movers mengikuti limit"
assert 'Tampilkan lebih banyak (+5)' in tgl and 'window.__tgmore[i]=from+5' in app, "tombol Top Movers menambah 5"
assert 'SGX(' not in tgl and 'Pre-ARA' not in tgl, "Top Gainer/Loser tidak menampilkan Pre-ARA"
print("OK: Top Gainer/Loser 5 awal +5 per klik pada semua tab; Pre-ARA tidak masuk daftar Top Movers")

# Momentum multi-hari harus memakai lima sesi bursa sebelumnya secara utuh.
assert "has5=H.length===5" in app, "momentum 5 sesi hanya dihitung bila lima data pembanding tersedia"
assert "if(has5)C.push(['Momentum multi-hari'" in app, "komponen momentum tidak boleh memakai histori parsial"
assert "penutupan 5 sesi bursa sebelumnya" in app, "keterangan momentum harus menyebut pembanding lima sesi bursa"
print("OK: momentum multi-hari memakai lima sesi bursa lengkap; histori parsial tidak menghasilkan skor momentum")
