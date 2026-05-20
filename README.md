# Android Forensic Ultra

Tool forensik perangkat Android via ADB — mirip MOBILedit Forensic Ultra.

## Fitur

- Deteksi perangkat Android otomatis (multi-device support)
- Log step-by-step persis seperti MOBILedit:
  - `Connecting device... OK`
  - `Rebooting... OK`
  - `Preparing decryption for Device Encrypted (DE) storage... OK`
  - `Device Encrypted (DE) storage was successfully decrypted`
  - `Preparing decryption for User 0... OK`
  - `User 0 was successfully decrypted`
  - `Processing done`
- Panel info perangkat (model, Android, root, enkripsi, boot mode)
- Ekstraksi 14 jenis data forensik
- Laporan JSON otomatis

## Persyaratan

- Python 3.10+
- ADB (`adb`) tersedia di PATH
- USB Debugging aktif di perangkat

## Instalasi

```bash
pip install -r requirements.txt
```

## Cara Pakai

```bash
# Deteksi perangkat otomatis
python android_forensics.py

# Pilih perangkat berdasarkan serial
python android_forensics.py -s SERIAL_PERANGKAT

# Tentukan direktori output
python android_forensics.py -o /kasus/kasus_001

# Hanya lihat info & log dekripsi (tanpa ekstraksi)
python android_forensics.py --skip-extract
```

## Output

Semua file disimpan di `forensic_<timestamp>/<serial>/`:

| File | Isi |
|------|-----|
| `packages.txt` | Semua package & path |
| `user_apps.txt` | Aplikasi yang diinstall pengguna |
| `processes.txt` | Proses yang sedang berjalan |
| `properties.txt` | Semua nilai `getprop` |
| `network.txt` | Interface jaringan |
| `routes.txt` | Tabel routing |
| `mounts.txt` | Mount point aktif |
| `accounts.txt` | Akun tersimpan (dumpsys) |
| `battery.txt` | Status baterai |
| `wifi.txt` | Status & jaringan WiFi |
| `telephony.txt` | Telephony registry dump |
| `notifications.txt` | Notifikasi aktif |
| `power.txt` | Info layar & kunci |
| `storage.txt` | Penggunaan storage |
| `laporan.json` | Laporan JSON lengkap |

> **Hanya untuk investigasi forensik yang resmi dan berotorisasi.**
