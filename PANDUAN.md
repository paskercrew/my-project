# Panduan Penggunaan Tool

## Daftar Tool

| File | Nama EXE | Fungsi |
|------|----------|--------|
| `forensic_gui.py` | `ForensicGUI.exe` | GUI mirip MOBILedit Forensic Ultra |
| `android_forensics.py` | `AndroidForensicUltra.exe` | CLI forensik semua Android |
| `frp_erase.py` | `SamsungFRPErase.exe` | Hapus FRP Samsung |
| `xiaomi_adb.py` | `XiaomiADB.exe` | Info + FRP Xiaomi/POCO |
| `edl_poco_x3.py` | `EdlPocoX3.exe` | **EDL Mode Poco X3 NFC** |

---

## Build Semua EXE

```cmd
Klik kanan build.bat -> Run as Administrator
```

---

## EDL Tool - Poco X3 NFC (SM7150)

### Cara Masuk EDL

**Via ADB (termudah - USB Debugging aktif):**
```cmd
EdlPocoX3.exe masuk-edl --via adb
```

**Via Fastboot (BL Unlock):**
```cmd
EdlPocoX3.exe masuk-edl --via fastboot
```

**Via Test Point (tanpa USB Debugging):**
1. Matikan HP
2. Short pad TP5 ke ground di PCB
3. Sambung USB ke PC
4. PC deteksi `Qualcomm HS-USB QDLoader 9008`

Lihat panduan lengkap:
```cmd
EdlPocoX3.exe test-point
```

### Cek EDL Mode
```cmd
EdlPocoX3.exe cek-edl
```

### Hapus FRP

**Via ADB (tanpa EDL):**
```cmd
EdlPocoX3.exe hapus-frp
```

**Via EDL (tanpa USB Debugging - perlu programmer):**
```cmd
EdlPocoX3.exe hapus-frp --edl --programmer prog_firehose_ddr.elf
```

### Dump Partisi via EDL
```cmd
# Dump satu partisi
EdlPocoX3.exe dump userdata --programmer prog_firehose_ddr.elf

# Dump beberapa partisi
EdlPocoX3.exe dump frp misc persist --programmer prog_firehose_ddr.elf

# Dump ke folder tertentu
EdlPocoX3.exe dump userdata -o D:\forensik --programmer prog_firehose_ddr.elf
```

### Tampilkan Info
```cmd
# Info perangkat + panduan EDL
EdlPocoX3.exe info

# Daftar partisi
EdlPocoX3.exe partisi
```

---

## Firehose Programmer (prog_firehose_ddr.elf)

File ini diperlukan untuk operasi EDL (dump partisi, erase).

**Cara mendapatkan:**
1. Download ROM MIUI untuk Poco X3 NFC (surya)
2. Ekstrak file `.tgz` / `.zip`
3. Cari file `prog_firehose_ddr.elf` di folder `images/`
4. Letakkan di folder yang sama dengan `EdlPocoX3.exe`

**Sumber ROM:**
- MIUI Official: xiaomi.eu atau miui.com
- Codename: `surya` (Global) / `karna` (China)

---

## Install edlclient (untuk operasi EDL lanjutan)

```cmd
pip install edlclient
```

Atau dari source:
```cmd
git clone https://github.com/bkerler/edlclient
cd edlclient
pip install -e .
```

> **Hanya untuk pemilik sah perangkat atau teknisi resmi.**
