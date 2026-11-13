@echo off
cd /d "%~dp0"
rem Jalankan SEKALI setelah menyalin zip. Memindahkan file lama/duplikat ke _arsip\ (tidak ada yang dihapus).
if not exist _arsip mkdir _arsip
for %%F in (paket_model_c upgrade_ke_model_c.py upgrade_ke_model_c.bat rollback_model_c.bat BACA_DULU.txt migrasi.bat telegram_worker.bat telegram_setup.py migrate.py validate.py backtest_amd_gate.py) do (
  if exist "%%F" move /y "%%F" "_arsip\" >nul && echo dipindah: %%F
)
for %%F in (static\sinyal.js static\ui-enhancements.js static\ui-enhancements.css) do (
  if exist "%%F" move /y "%%F" "_arsip\" >nul && echo dipindah: %%F
)
echo.
echo Selesai. Folder _arsip boleh dihapus kapan saja setelah aplikasi berjalan normal. rapikan.bat boleh dihapus.
pause
