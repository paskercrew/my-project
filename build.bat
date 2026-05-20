@echo off
chcp 65001 >nul
title Android Forensic Tools - Build EXE

echo ============================================================
echo   Android Forensic Tools - Build EXE untuk Windows
echo ============================================================
echo.

REM Cek Python tersedia
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python tidak ditemukan!
    echo Unduh di: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/5] Install dependensi...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Gagal install dependensi.
    pause
    exit /b 1
)
echo       OK
echo.

REM Buat folder output
if not exist dist mkdir dist

echo [2/5] Build AndroidForensicUltra.exe ...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "AndroidForensicUltra" ^
    --distpath dist ^
    --workpath build_tmp\forensic ^
    --specpath build_tmp ^
    android_forensics.py
if errorlevel 1 (
    echo [ERROR] Build AndroidForensicUltra.exe gagal.
    pause
    exit /b 1
)
echo       OK - dist\AndroidForensicUltra.exe
echo.

echo [3/5] Build SamsungFRPErase.exe ...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "SamsungFRPErase" ^
    --distpath dist ^
    --workpath build_tmp\frp ^
    --specpath build_tmp ^
    frp_erase.py
if errorlevel 1 (
    echo [ERROR] Build SamsungFRPErase.exe gagal.
    pause
    exit /b 1
)
echo       OK - dist\SamsungFRPErase.exe
echo.

echo [4/5] Build XiaomiADB.exe ...
pyinstaller --onefile --console --clean --noconfirm ^
    --name "XiaomiADB" ^
    --distpath dist ^
    --workpath build_tmp\xiaomi ^
    --specpath build_tmp ^
    xiaomi_adb.py
if errorlevel 1 (
    echo [ERROR] Build XiaomiADB.exe gagal.
    pause
    exit /b 1
)
echo       OK - dist\XiaomiADB.exe
echo.

echo [5/5] Bersihkan file sementara...
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
