# Katalis free float di sinyal Telegram

Sinyal Telegram sekarang menampilkan konteks transisi free float minimum 15% BEI. Aturan resmi yang dipakai adalah Peraturan I-A, Kep-00045/BEI/03-2026, efektif 31 Maret 2026. Tahap transisi ditentukan dari kapitalisasi pasar dan free float pada 31 Maret 2026:

| Kondisi per 31 Maret 2026 | Target | Tenggat |
| --- | --- | --- |
| Kapitalisasi pasar minimal Rp5 triliun, free float di bawah 12,5% | 12,5%, lalu 15% | 31 Maret 2027, lalu 31 Maret 2028 |
| Kapitalisasi pasar minimal Rp5 triliun, free float 12,5% hingga di bawah 15% | 15% | 31 Maret 2027 |
| Kapitalisasi pasar di bawah Rp5 triliun, free float di bawah 15% | 15% | 31 Maret 2029 |

## Data emiten yang diimpor

File `idx-free-float-31mar2026-2026-11-12.csv` telah dimasukkan ke `pkg/data/free_float_status.csv` sebanyak 956 emiten. Sinyal memakai kolom `% Free Float`, `Wajib FF`, dan `Batas Waktu / Status` sebagaimana tercantum dalam file. Tanggal snapshot dicatat sebagai 12 November 2026 berdasarkan nama file.

Untuk status berupa tanggal, sinyal membandingkan `% Free Float` dengan `Wajib FF`, lalu menampilkan target, tenggat, dan selisihnya. Status lain seperti `Telah Memenuhi`, `N/A`, `Force Delisting`, `Voluntary Delisting`, dan pengecualian ditampilkan sesuai teks dari file.

File impor tidak menyatakan secara eksplisit bahwa kolom kapitalisasi pasar dan free float adalah nilai dasar tepat per 31 Maret 2026, serta tidak menyediakan tautan sumber per emiten. Karena itu, angka kapitalisasi pasar disimpan sebagai data laporan tetapi tidak dipakai untuk menyimpulkan ulang kelompok transisi. Nama file disimpan sebagai provenance, bukan verifikasi sumber BEI. Ringkasan saham harian menyediakan `Listed Shares` dan `Tradeble Shares`, tetapi keduanya tidak otomatis dianggap sebagai free float resmi. Harga tertinggi harian juga tidak membuktikan saham terkunci di ARA atau order benar-benar terisi.

Teks sinyal menyebut selisih dalam poin persentase dari rasio yang ada di file. Angka itu konteks potensi pasokan, bukan prediksi harga atau rekomendasi transaksi. Data dasar kapitalisasi dan rasio tetap perlu diverifikasi dari sumber BEI/perusahaan tercatat; perubahan jadwal oleh BEI hanya berlaku sesuai persetujuan atau perintah OJK.

## Penalti risiko pada skor beli

Untuk emiten dengan tenggat tanggal yang tercantum dan rasio saat ini di bawah kewajibannya, skor beli dikurangi dengan heuristik:

`penalti = min(batas, kekurangan poin persentase × bobot × urgensi tenggat)`

Urgensi naik mendekati tenggat dan mencapai 1 setelah tenggat. Default: 1 poin skor per 1 poin persentase kekurangan, maksimum 10 poin, horizon urgensi 1.095 hari. Penalti hanya berlaku pada sinyal BUY terkonfirmasi, termasuk reversal; sinyal potensi/ARA dikecualikan. Status `Telah Memenuhi`, `N/A`, delisting, dan pengecualian tidak mendapat penalti. Skor dasar dan skor setelah penalti ditampilkan di dashboard/pesan Telegram. Bobot ini heuristik dan belum dikalibrasi melalui backtest.

Snapshot bisa diperbarui melalui **Input data → Tanggal snapshot free float → Update free float**. Sistem memvalidasi kolom, kode duplikat, rasio, dan kapitalisasi; menyimpan snapshot aktif serta mengarsipkan salinan per tanggal di `pkg/data/free_float_snapshots/`.
