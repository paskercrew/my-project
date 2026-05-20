@echo off
chcp 65001 >nul
title Android Forensic Suite - Build EXE

echo ============================================================
echo   Android Forensic Suite - Build EXE untuk Windows
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Unduh di: https://www.python.org/downloads/
    pause & exit /b 1
)

echo [1/3] Install dependensi...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERROR] Gagal install. & pause & exit /b 1 )
echo       OK
echo.

if not exist dist mkdir dist

echo [2/3] Build ForensicSuite.exe  ^(ALL IN ONE^)...
pyinstaller --onefile --windowed --clean --noconfirm ^
    --name "ForensicSuite" ^
    --distpath dist ^
    --workpath build_tmp ^
    --specpath build_tmp ^
    --hidden-import customtkinter ^
    --collect-all customtkinter ^
    --add-data "device_db.json;." ^
    main.py
if errorlevel 1 ( echo [ERROR] Build gagal. & pause & exit /b 1 )
echo       OK - dist\ForensicSuite.exe
echo.

echo [3/3] Bersihkan file sementara...
if exist build_tmp rmdir /s /q build_tmp
echo       OK
echo.

echo ============================================================
echo   BUILD SELESAI!
echo ============================================================
echo.
echo Jalankan: dist\ForensicSuite.exe
echo.
dir dist\ForensicSuite.exe
echo.
pause
