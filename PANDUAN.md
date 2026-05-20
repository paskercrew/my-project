# Panduan Penggunaan Tool

Repository ini berisi tiga tool forensik Android:

---

## 1. Android Forensic Ultra (`android_forensics.py`)

Mirip **MOBILedit Forensic Ultra** — koneksi, dekripsi, dan ekstraksi data forensik.

```bash
python android_forensics.py              # auto-detect perangkat
python android_forensics.py -s SERIAL   # target serial tertentu
python android_forensics.py --skip-extract  # info saja
```

---

## 2. Samsung FRP Erase Tool (`frp_erase.py`)

Mirip **UnlockTool** — hapus FRP Samsung via ADB.

```bash
python frp_erase.py              # auto-detect perangkat
python frp_erase.py -s SERIAL   # target serial tertentu
python frp_erase.py --info-only  # baca info saja
```

---

## 3. Xiaomi / Poco X3 NFC ADB Tool (`xiaomi_adb.py`)

Khusus untuk Xiaomi / POCO — baca info MIUI, cek Mi Account, hapus FRP, ekstraksi data.

```bash
# Baca info saja
python xiaomi_adb.py --info-only

# Hapus Google FRP + Mi Account
python xiaomi_adb.py --hapus-frp

# Ekstraksi data forensik
python xiaomi_adb.py --ekstrak

# Semua sekaligus
python xiaomi_adb.py --hapus-frp --ekstrak -o /kasus/poco_x3

# Target serial tertentu
python xiaomi_adb.py -s RF8W90VTNGX --hapus-frp
```

### Info yang ditampilkan (Poco X3 NFC):
- Merek, Model, Codename (`surya` / `karna`)
- Platform / SoC (Snapdragon 732G → `sm7150`)
- Versi MIUI & Android SDK
- Serial, Build ID, Security Patch
- Status Bootloader: **LOCKED / UNLOCKED**
- Status Mi Account (aktif / tidak)
- Status Google FRP
- Status Root

### Catatan khusus MIUI / Poco X3 NFC:
> Di MIUI, aktifkan **USB Debugging (Security)** di
> Pengaturan → Opsi Pengembang → USB Debugging (Security Settings)
> agar perintah ADB bisa memodifikasi data sistem.

---

## Instalasi

```bash
pip install -r requirements.txt
```

> **Hanya untuk pemilik sah perangkat atau teknisi resmi.**
