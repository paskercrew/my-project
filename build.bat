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

echo [1/6] Install dependensi...
pip install -r requirements.txt --quiet
if errorlevel 1 ( echo [ERROR] Gagal install. & pause & exit /b 1 )
echo       OK
echo.

if not exist dist mkdir dist

echo [2/6] Build ForensicGUI.exe  ^(GUI - mirip MOBILedit^)...
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

echo [3/6] Build AndroidForensicUltra.exe  ^(CLI^)...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "AndroidForensicUltra" ^
    --distpath dist --workpath build_tmp\forensic --specpath build_tmp ^
    android_forensics.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\AndroidForensicUltra.exe
echo.

echo [4/6] Build SamsungFRPErase.exe...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "SamsungFRPErase" ^
    --distpath dist --workpath build_tmp\frp --specpath build_tmp ^
    frp_erase.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\SamsungFRPErase.exe
echo.

echo [5/6] Build XiaomiADB.exe...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "XiaomiADB" ^
    --distpath dist --workpath build_tmp\xiaomi --specpath build_tmp ^
    xiaomi_adb.py
if errorlevel 1 ( echo [ERROR] Gagal. & pause & exit /b 1 )
echo       OK - dist\XiaomiADB.exe
echo.

echo [6/6] Bersihkan file sementara...
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
