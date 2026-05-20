# Panduan Penggunaan Tool

Repository ini berisi tiga tool forensik Android + build script untuk membuat file `.exe` Windows.

---

## Cara Build File .EXE (Windows)

### Syarat:
- **Python 3.10+** sudah terinstall dan ada di PATH
- **ADB** sudah terinstall (`adb` tersedia di CMD)

### Langkah:

**Cara 1 — Double-click (termudah):**
1. Klik kanan file `build.bat` → **Run as Administrator**
2. Tunggu sampai selesai
3. File `.exe` muncul di folder `dist\`

**Cara 2 — PowerShell:**
```powershell
# Klik kanan build.ps1 -> Run with PowerShell
# atau dari terminal:
powershell -ExecutionPolicy Bypass -File build.ps1
```

**Cara 3 — Manual satu per satu:**
```cmd
pip install -r requirements.txt
pyinstaller --onefile --console --name AndroidForensicUltra android_forensics.py
pyinstaller --onefile --console --name SamsungFRPErase frp_erase.py
pyinstaller --onefile --console --name XiaomiADB xiaomi_adb.py
```

### Hasil build:
```
dist\
├── AndroidForensicUltra.exe   ← Mirip MOBILedit Forensic Ultra
├── SamsungFRPErase.exe        ← Mirip UnlockTool (Samsung FRP)
└── XiaomiADB.exe              ← Khusus Xiaomi / Poco X3 NFC
```

---

## Cara Pakai EXE

Buka **CMD** atau **PowerShell** di folder `dist\`, lalu:

```cmd
# Tool 1 - Android Forensic (semua merek)
AndroidForensicUltra.exe
AndroidForensicUltra.exe -s SERIAL_PERANGKAT
AndroidForensicUltra.exe --skip-extract

# Tool 2 - Samsung FRP Erase
SamsungFRPErase.exe
SamsungFRPErase.exe -s SERIAL
SamsungFRPErase.exe --info-only

# Tool 3 - Xiaomi / Poco X3 NFC
XiaomiADB.exe --info-only
XiaomiADB.exe --hapus-frp
XiaomiADB.exe --ekstrak
XiaomiADB.exe --hapus-frp --ekstrak
```

---

## Install ADB di Windows

1. Unduh **Platform Tools**: https://developer.android.com/studio/releases/platform-tools
2. Ekstrak ke `C:\adb\`
3. Tambahkan `C:\adb\` ke **PATH** Windows:
   - Cari "Environment Variables" → Edit PATH → New → `C:\adb\`
4. Test: buka CMD → ketik `adb version`

---

## Install Python di Windows

1. Unduh di: https://www.python.org/downloads/
2. Centang **"Add Python to PATH"** saat instalasi
3. Test: buka CMD → ketik `python --version`

---

> **Hanya untuk pemilik sah perangkat atau teknisi resmi.**
