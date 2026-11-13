@echo off
setlocal
cd /d "%~dp0"
set PY=
for %%V in (3.12 3.13 3.11) do ( if not defined PY ( py -%%V --version >nul 2>&1 && set PY=py -%%V ) )
if not defined PY set PY=py
:menu
echo.
echo ===== ALAT STOCK SCREENER =====
echo  1. Hubungkan bot Telegram ^(simpan chat_id^)
echo  2. Jalankan worker Telegram saja
echo  3. Backtest reversal AMD ^(6 bulan^)
echo  4. Jalankan semua tes
echo  5. Migrasi data lama + validasi ^(sekali pakai^)
echo  0. Keluar
set /p P=Pilih:
if "%P%"=="1" %PY% telegram_worker.py --setup
if "%P%"=="2" %PY% telegram_worker.py
if "%P%"=="3" %PY% tools\backtest_amd_gate.py
if "%P%"=="4" for %%T in (tools\test_*.py) do (echo --- %%T & %PY% %%T)
if "%P%"=="5" ( %PY% tools\migrate.py --csv-dir data & %PY% tools\validate.py --csv-dir data )
if "%P%"=="0" exit /b 0
goto menu
