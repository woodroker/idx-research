@echo off
setlocal
cd /d "%~dp0"
title Stock Screener

rem --- pilih Python yang punya paket siap-pakai (3.12 / 3.13 paling aman); Python terlalu baru sering belum punya wheel pandas ---
set PY=
for %%V in (3.12 3.13 3.11) do (
  if not defined PY (
    py -%%V --version >nul 2>&1 && set PY=py -%%V
  )
)
rem --- fallback ke instalasi Python per-user yang sudah dipakai mesin ini ---
if not defined PY if exist "%LOCALAPPDATA%\Python\bin\python.exe" (
  "%LOCALAPPDATA%\Python\bin\python.exe" -c "import flask,dotenv,pandas,yfinance,openpyxl,xlrd" >nul 2>&1 && set PY="%LOCALAPPDATA%\Python\bin\python.exe"
)
if not defined PY set PY=py
%PY% --version
if errorlevel 1 (
  echo Python tidak ditemukan. Pasang Python 3.12 dari python.org ^(centang "Add to PATH"^).
  pause & exit /b 1
)

rem --- pasang dependency hanya bila belum lengkap; --only-binary = TIDAK PERNAH mengompilasi (tidak butuh Visual Studio) ---
%PY% -c "import flask,dotenv,pandas,yfinance,openpyxl,xlrd" >nul 2>&1
if errorlevel 1 (
  echo Memasang dependency ^(paket siap-pakai saja^)...
  %PY% -m pip install --only-binary=:all: -r requirements.txt
  if errorlevel 1 (
    echo.
    echo Gagal memasang dependency. Penyebab paling umum: versi Python terlalu baru ^(belum ada paket pandas untuknya^).
    echo Solusi: pasang Python 3.12 dari python.org, lalu jalankan run.bat lagi ^(otomatis memakai 3.12^).
    pause & exit /b 1
  )
)

%PY% server.py
pause
