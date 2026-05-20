# Panduan Penggunaan Tool

Repository ini berisi dua tool forensik Android:

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

Mirip **UnlockTool** — hapus FRP (Factory Reset Protection) Samsung via ADB.

```bash
python frp_erase.py              # auto-detect perangkat
python frp_erase.py -s SERIAL   # target serial tertentu
python frp_erase.py --info-only  # baca info saja, tanpa hapus FRP
```

### Info yang ditampilkan:
- Model, Manufacturer, Platform, CPU Arch
- Android Serial, Manufacturing Date, Security Patch
- Android Version, SDK, Build ID, Build Date
- BL / PDA / CP / CSC
- Sales Code
- Status root & permission

---

## Instalasi

```bash
pip install -r requirements.txt
```

> **Hanya untuk pemilik sah perangkat atau teknisi resmi.**
