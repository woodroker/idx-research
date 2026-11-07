STOCK SCREENER - MODEL C : SUMBER DATA TUNGGAL = SQLite (screener.db)

LANGKAH PAKAI (Windows)
1. Salin isi folder ini ke folder proyek Anda (timpa server.py, database.py, run.bat, requirements.txt,
   templates/index.html). screener.db yang sudah ada otomatis dinaikkan ke skema v2 (data tidak dihapus).
   Simpan dulu index.html lama sebagai cadangan.
2. Jalankan migrasi.bat  -> backup -> impor data tertanam + arsip data/*.csv -> validasi.
3. Jalankan run.bat, buka http://127.0.0.1:5000 di browser yang SAMA seperti biasa.
   Isi IndexedDB lama dibaca sekali & dimasukkan ke SQLite (hanya mengisi yang belum ada; tidak menimpa;
   data di browser tidak dihapus).
4. Jalankan lagi:  py validate.py --usr-json (opsional) . Kode HASIL: LULUS = aman menonaktifkan penyimpanan lama.

ALUR BARU
  upload (.xlsx/.xls/.csv) -> server mem-parse (parsers.py) -> simpan ke screener.db -> dashboard memuat /api/data
  - Rumus/tabel/grafik dashboard TIDAK diubah; D (px, days, tipe, sat, kl, nm, klc, hc) berbentuk sama persis.
  - Satu dataset per (jenis, tanggal): tanggal sama diperbarui, tanggal baru ditambahkan (UNIQUE di database).
  - Penimpaan dicatat di audit_log; bila jumlah baris turun (file parsial) muncul peringatan.
  - Penyimpanan jumlah saham manual (hc) disimpan ke database lewat /api/hc.
  - Tombol "Reset upload" kini hanya memuat ulang dari DB (tidak menghapus apa pun).
  - Pustaka XLSX di browser dihapus (parsing di server); index.html turun dari 3,8 MB menjadi ~140 KB
    karena data tertanam dipindah ke database.
  - Arsip data/*.csv tetap ditulis sebagai cadangan mentah, bukan sumber kalkulasi.

PERUBAHAN PERILAKU (disengaja)
  1. File berisi BANYAK tanggal (tipe/>=1%/klasifikasi) dipisah per tanggal. Dulu semua baris dimasukkan ke tanggal baris terakhir.
  2. Data >=1% dengan persentase >100 ditolak & dilaporkan. Dulu tersimpan lalu dimuat sebagai 0 setelah reload.
  3. Sumber ganda tanggal sama (mis. "Ringkasan Saham-20261103.csv" dan "Ringkasan_Saham-20261103.csv") -> yang terbaru dipakai, dicatat di audit_log.

HARGA TERBARU DARI YFINANCE (otomatis, mengisi panel yang sudah ada)
  - live.py mengisi dataset px (kode tanpa .JK, 17 kolom sama dgn Ringkasan IDX) untuk tanggal LEBIH BARU dari px resmi terakhir.
  - Otomatis tiap 5 menit selama jam bursa (Sen-Jum 08:55-16:15 WIB) + sekali setelah tutup + saat server start.
    Ubah interval: set SCREENER_YF_INTERVAL=120 | matikan: set SCREENER_YF=0 | manual: tombol "Update harga (yfinance)".
  - Dashboard memuat ulang data sendiri (cek tiap 30 dtk) bila ada pembaruan; tidak dilakukan bila jendela detail saham terbuka.
  - Pengaman: tanggal resmi (IDX/CSV) TIDAK PERNAH ditimpa yfinance; unggahan Ringkasan IDX untuk tanggal itu otomatis
    menggantikan data yfinance; kalibrasi harga & satuan volume terhadap data resmi terakhir (gagal -> batal, tidak menulis);
    prev close diambil dari penutupan resmi; data KSEI (days/tipe/sat/kl) dan nama emiten tidak pernah disentuh.
  - Kolom yang tidak ada di yfinance: foreign buy/sell, frekuensi, bid/offer = 0 (kosong sampai file IDX hari itu diunggah);
    nilai transaksi = estimasi vol x (H+L+C)/3; saham beredar dibawa dari data resmi terakhir.
    Akibatnya sinyal berbasis foreign net / bid-offer pada hari yang baru berasal dari yfinance belum lengkap.
  - Data tertunda ~10-15 menit & tidak resmi. Butuh: py -m pip install yfinance  (sudah di requirements.txt).

WATCHLIST & ANIMASI
  - Panel Watchlist di bawah Top Gainer/Loser: ketik kode (ada saran otomatis dari daftar emiten) lalu +, klik baris untuk detail,
    ✕ untuk hapus. Tersimpan di SQLite (tabel user_watchlists, user 'local'), tetap ada setelah reload. Kolom 5h muncul bila >=6 hari data harga.
  - Top Gainer/Loser Mingguan diringkas 3 baris (harian tetap 5).
  - Animasi: baris saham yang harganya berubah saat data diperbarui (yfinance/unggah) berkedip hijau (naik) / merah (turun) ~1,8 dtk
    di tabel, Top Gainer/Loser, dan Watchlist. CSS murni (menghormati 'reduce motion'), bukan komponen React.

TAB FUNDAMENTAL (panel detail emiten)
  Klik emiten -> tab "Fundamental" (di samping "Analisis"): 8 kartu metrik, kuadran valuasi & skor kualitas (8 uji), peringatan,
  posisi harga 52 minggu, tombol Detail (tabel tahunan & kuartalan). Warna/font mengikuti tema gelap dashboard.
  Sumber: yfinance (tidak resmi) via /api/fundamental/<kode>; di-cache 12 jam di SQLite (tabel fundamentals_cache), maks 1 permintaan/dtk.
  SKOR GABUNGAN (maks 14) = ROE + PBV + DER + PE + NPM + EPS-growth (ambang di bagian atas fundamentals.py):
    ROE >15%:+3 | 10-15%:+2 | <10%:0      PBV <1,0x:+3 | 1,0-1,5x:+2 | >1,5x:0      DER <1,0x:+2 | 1,0-1,5x:+1 | >1,5x:-2 (n/a utk sektor keuangan)
    PE <10x:+2 | 10-15x:+1 | >15x atau rugi:0      NPM >15%:+2 | 10-15%:+1 | <10%:0      EPS (pendekatan: laba YoY) >5%:+2 | 0-5%:+1 | turun:-1
    Komponen tanpa data = n/a, skor dinormalisasi ke 14 (butuh >=4 komponen). 11-14 Mutiara Super | 7-10 Wajar/Layak Pantau | <7 Hindari.
  KUADRAN: Y = ROE (>15% & NPM>10%) | X = PBV<1,5x & PE<15x. I Undervalued | II Growth/Premium | III Value Trap (ROE<10% & PBV<1) | IV Overvalued
    | "Mendekati Kuadran I" (ROE 10-15%, murah) | Zona Tengah (di luar keempat kuadran).
  SINYAL fundamental (urutan = prioritas):
    WAIT  data belum cukup (<4 komponen skor)
    SELL  laba 12 bulan negatif, ATAU skor <7
    BUY   skor >=11 DAN kuadran I/mendekati I DAN DER <=1,5x (atau keuangan) DAN PE 0-15x
    HOLD  skor >=11 tetapi tidak lolos filter (mahal / DER tinggi / PE belum konfirmasi), ATAU skor 7-10 di kuadran I/II/mendekati I
    WAIT  skor 7-10 di Zona Tengah / Kuadran III (pantau dulu)
    Kartu hanya menampilkan label BUY/HOLD/SELL/WAIT; alasan & 4 cek (Skor>=11, Kuadran I, DER<=1,5x, PE<15) ada di tooltip. Valuasi = label singkat (Undervalued, Growth, Value Trap, Overvalued, Near Undervalued, Zona Tengah) + bar 4 segmen (makin penuh makin menarik) + angka kuadran + skor/14. Rincian skor ada di tombol Detail Fundamental. Sinyal ini FUNDAMENTAL saja, belum digabung dgn keputusan MODEL C.
  8 'Uji kualitas' (laba positif, ROE>=COE, laba/penjualan tumbuh, margin, utang, BV/saham, ROE stabil) tetap ditampilkan sebagai chip.
  Dividend yield dihitung dari dividen 12 bulan / harga (bukan field yfinance), ditandai bila >25%. Cakupan data yfinance utk saham kecil IDX
  tidak merata. Uji: python tools/test_fundamentals.py

HALAMAN DEPAN
  Tabel Akumulasi/Distribusi: 25 baris (tombol "Tampilkan lebih banyak" +25). Kolom baru "Holder" (sesudah % saham, bisa diurutkan):
  jumlah pemegang aktif >=5% (data 5% terbaru) + 1-5% (data 1% terbaru); yang sudah keluar (kepemilikan 0) tidak dihitung; arahkan kursor = rincian.
  (Kartu "Holder terbanyak" sudah dihapus.)

KEPUTUSAN GABUNGAN = SATU-SATUNYA LABEL BUY/HOLD/SELL/WAIT + SKOR di seluruh dashboard
  Dipakai di: kartu di bawah header panel emiten (tab Analisis & Fundamental) dan halaman BUY / SELL (label, skor, filter Buy/Hold/Wait/Sell, hitungan).
  Tombol/skor BUY lama di blok Analisis dan tombol BUY di tab Fundamental sudah dihapus. Hasil BSX asli tetap jadi komponen & sumber OTE/stop/target.
  K (-100..+100) = rata-rata berbobot komponen yang ADA. Bobot/ambang: objek FW di index.html (cari "const FW="):
    Arus dana 35% (skor akumulasi KSEI) | Teknikal 25% (skor BSX) | Dini 10% (aktivitas harian) | Fundamental 30% ((skor14-7)/7*100)
  SELL: K<=-30, atau arus dana<=-45, atau (teknikal/fundamental SELL bersama arus dana<=-15)
  BUY : K>=30 dan arus dana>=15 dan teknikal & fundamental bukan SELL | HOLD: K>=30 tertahan gerbang, atau 10<=K<30 | WAIT: selainnya / data kurang
  Fundamental utk halaman daftar dibaca dari cache SQLite (/api/fundamental/cached). Antrean latar mengambil fundamental watchlist + 40 kandidat teratas pelan-pelan
  (1 emiten/5 dtk, maks 120/hari, istirahat 20 menit bila kena limit; atur SCREENER_FUND_DAILY, SCREENER_FUND_GAP).

DATA FUNDAMENTAL & HARGA PENUTUPAN DI SQLITE
  Fundamental: tabel fundamentals_cache (kode, fetched_at, payload_json = info + 8 kuartal + 3 tahunan mentah dari yfinance); skor/kuadran dihitung saat dibaca.
  Harga tutup: shared_records (jenis px), payload[0]=close, [1]=close sebelumnya, [2]=volume; shared_datasets.origin = upload / csv / yfinance.
  Cek di komputer Anda:  py -c "import sqlite3;c=sqlite3.connect('screener.db');print(c.execute('select security_code,fetched_at from fundamentals_cache').fetchall()[:5])"

NOTIFIKASI TELEGRAM (harga masuk zona OTE sisi beli)
  Pasang: 1) kirim /start ke bot Anda  2) py telegram_setup.py (mengisi chat_id & mengaktifkan)  3) run.bat. Baris "Telegram" di sidebar: ON/OFF dan Tes.
  Isi   : Emiten / Status: masuk area OTE - harga sekarang / Stop / Target TP 1 / Target TP 2 / Skor kualitas (skor fundamental/14 - kuadran).
  Syarat: dashboard terbuka (perhitungan OTE ada di browser), bursa buka (WIB), data harga hari ini, harga di dalam zona OTE, stop<harga<TP1<TP2.
  Aman  : jeda >=4 dtk antar pesan, maks 20 pesan/hari, maks 5 per kiriman, 1 notifikasi per emiten per hari (alert_log, aman saat restart), HTTP 429 menunggu
          retry_after, token salah/bot diblokir -> otomatis berhenti. Semua di telegram.json (max_per_day, min_gap_sec, dst).
  KEAMANAN: token hanya di server (telegram.json), tidak dikirim ke browser. Token sudah tertulis di chat -> sebaiknya dibuat ulang via @BotFather (/revoke) setelah uji.
  Uji   : python tools/test_telegram.py (HTTP palsu, tidak mengirim apa pun).

FONT & TOMBOL: satu font (JetBrains Mono, font homepage) di seluruh dashboard; semua tombol/label aksi persegi (tanpa sudut membulat).

TATA LETAK SIDEBAR
  Watchlist (atas) > Top Gainer/Loser > widget live yfinance > Input data (bawah).
  Widget live: titik & garis denyut (hijau=live, kuning=memuat, merah=error, abu=bursa tutup/manual), bar naik/datar/turun pasar
  (dihitung dari harga terbaru), jam update, garis hitung mundur ke update berikutnya, tombol ⟳. Arahkan kursor untuk detail/error.

JENIS DATA BARU (mis. affiliate)
  Format yang tidak dikenali parser ditolak dengan pesan "format tidak dikenali" dan TIDAK mengubah database.
  Untuk mendukung jenis baru: kirim 5 baris pertama file (header), lalu ditambahkan cabang parser + jenis dataset baru.

UPDATE HARIAN KSEI
  Unggah seperti biasa. Tiap jenis & tanggal hanya satu dataset (tidak bisa ganda); mengunggah ulang file yang sama = tidak berubah;
  file yang tanggalnya sudah ada = diperbarui & tercatat di audit_log; jumlah baris turun = peringatan.

FILE
  live.py       pengisi px dari yfinance + kalibrasi
  server.py     endpoint: /api/upload /api/data /api/hc /api/migrate/legacy /api/status /api/live/update
  parsers.py    port 1:1 parse(), n(), iso(), SAN() dari index.html lama
  store.py      simpan/ganti dataset, bangun D dari SQLite
  database.py   skema v2 + upgrade + backup (backups/)
  importer.py   pembaca sumber lama   |  migrate.py / validate.py  |  tools/test_parser_parity.py
  legacy/       legacy_embedded_D.json (data tertanam di HTML lama), parse_asli.js (untuk uji paritas)

YANG SUDAH DIUJI / BELUM
  Sudah: parser Python == parse() asli (Node) untuk 5 jenis file (sintetis); data tertanam -> SQLite -> D identik
  (27 dataset, 1011 kode, sidik jari kalkulasi cocok); upgrade screener.db v1 kosong Anda; upload CSV & XLSX via UI
  headless; simpan hc; migrasi IndexedDB (fill-only, konflik dipertahankan); ETag 304; upload ulang idempoten.
  BELUM: 318 CSV asli Anda tidak ada pada saya (hanya laporan header) -> jalankan migrasi.bat lalu baca hasil validate.
  Cloud (window.claude db) tidak dapat diakses dari luar sesi aslinya; bila ada data hanya di sana, buka dashboard lama
  di lingkungan itu, ekspor, lalu pakai:  py migrate.py --usr-json hasil_ekspor.json
  Tes browser memakai stub React/Chart.js (CDN tak terjangkau); error "RR ... destructure 'C'" juga muncul di HTML asli.
