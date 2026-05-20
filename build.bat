@echo off
chcp 65001 >nul
title Android Forensic Tools - Build EXE

echo ============================================================
echo   Android Forensic Tools - Build EXE untuk Windows
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Unduh di: https://www.python.org/downloads/
    pause & exit /b 1
)

echo [1/7] Install dependensi...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERROR] Gagal install. & pause & exit /b 1 )
echo       OK
echo.

if not exist dist mkdir dist

echo [2/7] Build ForensicGUI.exe  ^(GUI - mirip MOBILedit^)...
pyinstaller --onefile --windowed --clean --noconfirm ^
    --name "ForensicGUI" ^
    --distpath dist --workpath build_tmp\gui --specpath build_tmp ^
    --hidden-import customtkinter ^
    --collect-all customtkinter ^
    --add-data "device_db.json;." ^
    forensic_gui.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\ForensicGUI.exe
echo.

echo [3/7] Build AndroidForensicUltra.exe  ^(CLI^)...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "AndroidForensicUltra" ^
    --distpath dist --workpath build_tmp\forensic --specpath build_tmp ^
    android_forensics.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\AndroidForensicUltra.exe
echo.

echo [4/7] Build SamsungFRPErase.exe...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "SamsungFRPErase" ^
    --distpath dist --workpath build_tmp\frp --specpath build_tmp ^
    frp_erase.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\SamsungFRPErase.exe
echo.

echo [5/7] Build XiaomiADB.exe...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "XiaomiADB" ^
    --distpath dist --workpath build_tmp\xiaomi --specpath build_tmp ^
    xiaomi_adb.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\XiaomiADB.exe
echo.

echo [6/7] Build EdlPocoX3.exe...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "EdlPocoX3" ^
    --distpath dist --workpath build_tmp\edl --specpath build_tmp ^
    --hidden-import serial ^
    edl_poco_x3.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\EdlPocoX3.exe
echo.

echo [7/7] Bersihkan file sementara...
if exist build_tmp rmdir /s /q build_tmp
echo       OK
echo.

echo ============================================================
echo   BUILD SELESAI!
echo ============================================================
echo.
echo File EXE tersimpan di folder: dist\
echo.
dir dist\*.exe
echo.
pause
