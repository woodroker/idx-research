# Penyaringan Potensi ARA BEI

## Acuan resmi


Untuk saham Papan Utama, Pengembangan, dan Ekonomi Baru: harga acuan Rp1–Rp10 memakai batas nominal +Rp1; Rp11–Rp200 +35%; >Rp200–Rp5.000 +25%; >Rp5.000 +20%. Untuk Papan Akselerasi dan Pemantauan Khusus, Rp1–Rp10 memakai +Rp1 dan harga di atas Rp10 memakai +10%. Harga hasil hitung dibulatkan ke bawah ke fraksi harga yang berlaku pada harga batas. Status papan tidak tersedia dalam data ringkasan saat ini, sehingga scanner menandai asumsi papan reguler dan tidak mengklaim batas aktual untuk emiten yang statusnya khusus. Tabel yang berlaku untuk transaksi lama harus diperiksa sesuai tanggalnya; aturan efektif 28 September 2026 tidak diterapkan ke tanggal sebelumnya.

## Kriteria screener

Tag Pre-ARA/Breakout menggabungkan batas resmi tadi dengan aturan teknikal yang sifatnya heuristik: relative volume, nilai transaksi, posisi close dalam rentang harian, kedekatan resistance 10/20 sesi, kompresi rentang, EMA20, dan porsi volume candle naik. Nilai transaksi, proyeksi volume, skor, serta ambang adalah penyaring, bukan aturan BEI dan belum membuktikan edge.

Database Ringkasan Saham menyimpan snapshot bid/offer per tanggal: offer volume ada di kolom payload 12, bid volume di payload 14. Scanner hanya memakai rasio bila tanggal snapshot sama dengan tanggal bar. Rasio bid ≥2× offer menambah lima poin sebagai konfirmasi opsional; data ini bukan pembacaan order book berkelanjutan dan tidak memastikan antrean bertahan, momentum 5–15 menit, atau fill. HAKA, VWAP, dan sebaran transaksi intraday tidak tersedia dari candle harian YFinance yang dipakai worker.

## Cara membaca hasil

- “Pre-ARA” berarti kandidat teknikal sebelum resistance ditembus.
- “Breakout ARA” berarti breakout resistance terkonfirmasi, bukan ARA sudah tercapai.
- “Batas ARA tersentuh” pada panel Top Gainer hanya berarti high harian mencapai batas teoretis dengan asumsi papan reguler; itu tidak membuktikan harga terkunci atau order terisi.
- Periksa status papan, UMA, suspensi, FCA, likuiditas, dan biaya sebelum menafsirkan sinyal. Sinyal bersifat riset/edukasi, bukan rekomendasi atau jaminan.

## Batas validasi

Tes otomatis untuk formula dan alur hanya memeriksa kasus sintetik. Data historis terbaru dalam proyek belum cukup untuk mengklaim akurasi atau profitabilitas. Perlu validasi walk-forward pada data yang benar-benar tersedia saat keputusan dibuat, dengan biaya dan pemisahan kandidat, sentuhan batas, antrean terkunci, serta eksekusi aktual.

## Skor yang ditampilkan

### Radar kandidat Top Gainer
Radar memberi skor 0–100 sebagai peringkat relatif antar saham likuid pada tanggal data, bukan peluang atau prediksi return. Kandidat adalah 10% dengan peringkat tertinggi pada semesta saham yang memiliki sedikitnya 21 sesi OHLC dan rata-rata nilai transaksi 20 sesi sebelumnya minimal Rp250 juta. Faktor: rasio volume dan nilai transaksi terhadap rata-rata 20 sesi, return 1/5/20 sesi, posisi close pada rentang harian, serta proxy net asing lima sesi bila tersedia sedikitnya 3 hari Ringkasan resmi. Bobot dibulatkan dari AUC historis: volume 20,7; nilai transaksi 19,8; return 1 sesi 16,5; return 5 sesi 12,8; return 20 sesi 9,3; asing 8,7; posisi close 7,9. Komponen yang tidak tersedia dikeluarkan dari penyebut.

Label validasi adalah 20% teratas dari return open-to-close positif sesi berikutnya, sebagai proxy yang tidak membuktikan fill. AUC fitur tunggal hanya sekitar 0,52–0,58. Walk-forward menunjukkan presisi membaik pada sebagian setelan, tetapi return bersih rata-rata setelah biaya tetap negatif. Radar untuk watchlist riset, bukan sinyal beli atau klaim keunggulan.

### Skor ARA
Skor Pre-ARA memakai hard gate teknikal. Bonus asing maksimal 5 poin: +5 bila proxy net buy lima sesi sekurangnya 5% nilai transaksi, +3 bila sekurangnya 2%, +1,5 bila positif di bawah 2%, dan 0 bila netral/net sell. Aktif hanya jika tersedia minimal 3 hari Ringkasan resmi; jika kurang, komponen dikeluarkan dari penyebut. Proxy dihitung sebagai (foreign buy − foreign sell) × close lalu dibagi nilai transaksi. Ini bukan nilai transaksi asing persis. Bid/offer harian tetap heuristik, bukan antrean intraday.

Di Top Gainer dan notifikasi, skor disertai tanggal data dan faktor utama. Radar Top Gainer berbeda dari batas ARA resmi dan tidak membuktikan antrean terkunci atau fill.
