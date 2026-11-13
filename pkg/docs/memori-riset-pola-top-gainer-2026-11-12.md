# Memori riset: pola sebelum top gainer / ARA

**Tanggal riset:** 12 November 2026
**Semesta:** database `pkg/screener.db`, ringkasan saham harian BEI
**Tujuan:** mencari perilaku yang mendahului lonjakan, bukan menjelaskan mengapa sinyal lama gugur.

## Temuan utama

- Belum ada satu pola reversal yang konsisten sebelum saham menjadi top gainer. Jalur yang terlihat berbeda: sebagian saham bergerak dari volume sepi lalu melonjak; sebagian lain sudah naik beberapa hari; sebagian melonjak tanpa peningkatan volume yang terlihat pada sesi sebelumnya.
- Petunjuk kuantitatif paling berguna sejauh ini adalah **ekspansi aktivitas** (volume dan nilai transaksi relatif terhadap rata-rata 20 sesi), tetapi ia hanya menaikkan peluang secara moderat. Dalam studi prediksi top gainer sesi berikutnya, kuartil volume tertinggi memiliki tingkat top gainer 10,48% versus 5,63% di kuartil terendah (lift 1,86x); kuartil turnover tertinggi 10,58% versus 5,85% (lift 1,81x). Label top gainer di sini adalah 20% teratas dari return positif sesi target, bukan label ARA resmi.
- Momentum 5/20 sesi dan posisi close di dalam range sehari menunjukkan manfaat yang lebih kecil atau tidak konsisten. Net foreign dan snapshot bid/offer harian memberi tambahan pemisahan kecil; data ini tidak mendukung klaim bahwa keduanya merupakan tanda awal yang andal.
- Studi walk-forward yang sudah ada (`pkg/tools/backtest_top_gainer_flow.py`, output di `pkg/hasil_backtest_amd/top_gainer_20261112_openclose_proxy/`) mendukung kehati-hatian: pada fold out-of-sample 28 Sep–12 Nov 2026, model teknikal memilih 10% kandidat dengan precision top gainer 14,01% dibanding baseline 7,32%, tetapi rata-rata return open-to-close hari berikutnya setelah asumsi biaya tetap sekitar -1,02%. Model market-flow juga sekitar 13,91% precision dan -1,01% net. Seleksi lebih baik daripada baseline untuk label, tetapi belum menghasilkan expectancy bersih positif.

## Cakupan dan metode yang telah diperiksa

- Ada 187 sesi ringkasan harga dari 2 Feb sampai 12 Nov 2026, sekitar 179.629 record saham. Sekitar 158.081 record memiliki 17 kolom; 21.548 hanya memiliki close dan previous close. Karena itu, pengukuran OHLC, volume, turnover, foreign, serta bid/offer hanya memakai bar lengkap yang lolos pemeriksaan kelengkapan; data ini menghasilkan 118.208 bar lengkap dan median 628 saham per sesi.
- Studi eksplorasi membandingkan saham yang menjadi 20% top gainer dari return positif dengan saham lain, memakai fitur yang telah tersedia pada penutupan sebelum sesi target. Hasil event-aligned pada 6.701 kejadian satu sesi kemudian menunjukkan median relative volume 0,83x untuk calon top gainer dan 0,64x untuk kontrol; median relative turnover 0,79x dan 0,61x. Distribusinya berat ekor: rata-rata kejadian masing-masing 2,46x dan 2,71x. Jadi lonjakan aktivitas memberi petunjuk pada sebagian kasus, tetapi mayoritas pemenang tidak menunjukkan >1,5x volume/value sehari sebelumnya.
- Pada lag tiga dan lima sesi, median volume/value relatif hanya sedikit berbeda dari kontrol. Beberapa kasus besar mengangkat rata-rata, sehingga jangan memakai mean mentah sebagai ambang universal.
- Untuk 12 Nov 2026, contoh top gainers menunjukkan pola campuran: TRON (+34,48%) dan VKTR (+25,00%) tidak punya lonjakan volume/turnover di sesi sebelumnya; AGAR (+24,91%) punya sekitar 4,0x volume dan 3,9x turnover sehari sebelumnya; AIMS (+24,74%) sudah naik sekitar 70,9% dalam lima sesi sebelum sesi sebelumnya. High harian yang sama dengan batas teoritis bukan bukti harga terkunci atau order terisi.
- Semesta saham-sesi lengkap setelah aturan efektif 28 Sep hanya sekitar 16.183 observasi. Sentuhan batas ARA teoretis berbasis asumsi papan reguler jarang (0,88% pada satu sesi berikutnya, 2,83% dalam lima sesi). Jumlah peristiwa ARA kecil dan metadata papan tidak tersedia, jadi belum cukup untuk menyimpulkan pola ARA yang dapat diandalkan.

## Pembacaan regime pasar (proksi internal, bukan IHSG)

Pada 12 Nov, indeks equal-weight sederhana dari saham dengan bar lengkap berada sekitar 14,9% di bawah MA50; MA50 turun sekitar 7,2% dalam 20 sesi dan volatilitas realisasi 20 sesi tahunannya sekitar 55,8%, tertinggi dalam jendela database. Breadth harian terakhir tetap positif: sekitar 72,6% dari 592 saham lengkap naik pada 12 Nov. Ini lebih cocok disebut **tekanan turun bergejolak dengan pantulan breadth tajam**, dengan ketidakpastian tinggi. Ini bukan ukuran IHSG resmi, universe berubah antarhari, dan database belum memiliki 200 sesi untuk MA200.

## Implikasi untuk riset/pengembangan screener

1. Ubah fokus dari satu label `reversal` ke tahap perilaku yang bisa diuji: **basis/kontraksi → ekspansi volume/value dan range → close kuat atau breakout → follow-through / gagal**.
2. Ukur setiap tahap dengan fitur kausal dan outcome yang eksplisit untuk horizon 1, 3, dan 5 sesi; bandingkan terhadap baseline harian dan hitung hasil setelah biaya.
3. Pisahkan label **top gainer** (ranking lintas saham) dari **lonjakan absolut** (misalnya ambang return tetap) dan dari **sentuhan ARA teoretis**. Jangan campur ketiganya sebagai satu keberhasilan.
4. Perlakukan saham yang sudah naik tajam sebelum sinyal sebagai kelompok momentum lanjutan, bukan reversal dini. Hindari memberi nama “sebelum terbang” pada pola yang baru terlihat setelah pergerakan mulai berlangsung.
5. Jangan klaim validasi intraday dari data harian. Ringkasan harian hanya satu snapshot bid/offer dan OHLC; ia tidak merekam urutan antrean, pembatalan order, HAKA, atau fill dalam 5–15 menit.

## Arah riset lanjutan dari pengguna

- Karena Yahoo Finance menyediakan candle harian OHLCV tetapi tidak menyediakan riwayat order book/arus transaksi BEI, prioritaskan pola struktur harga yang bisa diamati: **4 Horsemen sebagai kandidat fase awal → MSS/BOS atau reversal sebagai konfirmasi → ekspansi volume/value dan rentang sebagai tanda transisi likuiditas → follow-through/top gainer/ARA**. Hipotesis pentingnya adalah saham yang awalnya sepi dapat mulai menjadi likuid sebelum lonjakan; uji volume dan turnover relatif tanpa mensyaratkan saham sudah likuid sejak awal.
- Pengguna menyebut TRON sebagai contoh pola 4 Horsemen sebelum naik, dan menyebut AGAR, IRSX, BUVA, serta NICL sebagai kandidat yang lolos pengamatan/uji; IRSX dan AGAR kemudian menjadi ARA/top gainer menurut pengamatan pengguna. Catat ini sebagai daftar studi kasus yang perlu dicocokkan dengan bar historis dan tanggal di database, bukan hasil verifikasi atau bukti bahwa polanya memprediksi lonjakan.
- Tujuan sinyal adalah menangkap fase awal perubahan struktur/aktivitas; jangan menjadikan syarat likuiditas awal yang tinggi sebagai filter gugur universal karena perubahan dari sepi ke aktif justru bagian pola yang diteliti. Evaluasi kandidat dan outcome secara terpisah.
- Implementasi lanjutan: `four_horsemen` muncul di filter/tabel dashboard dan sebagai satu alert POTENSI Telegram bila satu atau kedua aturan bullish terpenuhi: (1) candle 1 bearish, candle 2–4 bullish, `L4 > H2` dan `H2 < H1 < L4`; (2) empat candle hijau, close terakhir di atas EMA20, dan EMA20 menanjak. Bila keduanya cocok, satu alert mencantumkan keduanya. MSS/BOS, reversal, volume/value, dan rentang menaikkan prioritas tetapi bukan syarat gugur. Kandidat tidak dibuang hanya karena turnover di bawah lantai scanner umum; kuota Telegram harian/burst tetap berlaku. Stop/target berbasis candle harian OHLCV dan bukan bukti fill. Evaluasi contoh TRON, AGAR, IRSX, BUVA, NICL secara terpisah sebelum menyatakan aturan tervalidasi.

## Arahan BUY yang diminta pengguna dan implementasi awal

- Pengguna meminta pola riset diterapkan sebagai notifikasi BUY Telegram. Perlakukan sebagai paper/research alert; jangan menganggap temuan ini sudah membuktikan edge bersih karena fold out-of-sample sebelumnya masih negatif setelah asumsi biaya.
- Aturan awal `pre_takeoff_buy`: radar top 10% dari Ringkasan Saham pada sesi sebelumnya; radar harus cocok tanggal dengan candle sebelumnya; pada sesi berjalan harga menembus high 20 sesi, harga di atas open dan naik maksimal 8% (batas kejar yang dapat dikonfigurasi), posisi harga di ≥60% rentang hari berjalan, rentang hari ≥1,1× rata-rata 20 sesi, dan volume **atau** turnover proyeksi ≥1,5× rata-rata 20 sesi. Lantai likuiditas efektif default scanner Rp500 juta rata-rata turnover karena prafilter global `ara_min_value`, meski helper juga memiliki lantai konfigurasi Rp250 juta. Stop memakai low terendah lima sesi sebelum hari berjalan; alert hanya lolos jika jarak stop dalam batas konfigurasi. TP1/TP2 dibuat dari risiko harga 1,5R/3R untuk format kartu, bukan estimasi probabilitas.
- Data radar berasal dari snapshot Ringkasan Saham BEI sesi sebelumnya; pemicu harga/volume menggunakan candle 1 hari Yahoo Finance yang masih berjalan. Ketidakcocokan tanggal harus meniadakan alert. Preferensi tetap tampilan Telegram: hilangkan baris sumber/delay/waktu dan teks peringkat seperti `· peringkat 12/900` (termasuk format `n/universe`); tetap tampilkan skor radar, status 10% teratas, faktor pola, harga/stop/target, serta risiko harga per saham.
- Batas 1,5× dan 1,1× adalah ambang heuristik awal yang mengambil petunjuk dari studi eksplorasi; kompresi basis belum diukur dan fold out-of-sample tetap tidak profitable bersih. Jangan menyebut sinyal ini tervalidasi profitabel atau menjanjikan ARA/fill.

## Batas data dan aturan ARA

- Statistik ini eksploratif, observasi antarhari untuk saham yang sama saling berulang, tidak memakai news/UMA/suspensi, dan bukan bukti kausal atau jaminan keuntungan. Backtest lama menggunakan proksi return open-to-close, bukan bukti harga entry dapat dieksekusi.
- Database tidak memiliki metadata papan saham historis yang cukup. Perhitungan ARA harus diberi label **asumsi papan reguler**; high harian hanya menunjukkan sentuhan teoritis, bukan ARA terkunci/fill.
- Halaman mekanisme BEI yang diperiksa 12 Nov 2026 menyebut Kep-00136/BEI/09-2026 dan Kep-00137/BEI/09-2026 efektif 28 Sep 2026. Batas ARA resmi harus dihitung menurut tanggal dan papan; angka “Early ARA”/“Potensi ARA” tetap heuristik nonresmi. Sumber: [Mekanisme dan Jam Perdagangan BEI](https://www.idx.co.id/id/produk/mekanisme-dan-jam-perdagangan).

Analisis untuk riset dan edukasi, bukan nasihat keuangan.
