@echo off
cd /d "%~dp0"
echo === MIGRASI data lama ke screener.db (backup otomatis dibuat dulu) ===
py -m pip install -r requirements.txt
py migrate.py --csv-dir data
if errorlevel 1 goto gagal
echo.
echo === VALIDASI ===
py validate.py --csv-dir data
echo.
echo Selesai. Jalankan run.bat, buka http://127.0.0.1:5000 pada browser yang SAMA dengan sebelumnya
echo agar isi IndexedDB lama ikut dimigrasi otomatis (data di browser tidak dihapus).
pause
exit /b 0
:gagal
echo Migrasi gagal. Lihat pesan di atas.
pause
