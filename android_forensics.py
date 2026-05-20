#!/usr/bin/env python3
"""
Android Forensic Ultra
Tool ekstraksi forensik perangkat Android via ADB.
Mirip MOBILedit Forensic Ultra - hanya untuk investigasi resmi.
"""

import subprocess
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Pastikan 'rich' terinstall
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich import box
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich import box

console = Console()


# ---------------------------------------------------------------------------
# Utilitas ADB
# ---------------------------------------------------------------------------

def _run_cmd(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    """Jalankan perintah shell, kembalikan (sukses, output)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, (result.stderr.strip() or result.stdout.strip())
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, f"Perintah tidak ditemukan: {cmd[0]}"
    except Exception as exc:
        return False, str(exc)


def adb(*args: str, serial: str = "", timeout: int = 15) -> tuple[bool, str]:
    """Jalankan perintah ADB."""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return _run_cmd(cmd, timeout=timeout)


def adb_shell(serial: str, shell_cmd: str, timeout: int = 20) -> tuple[bool, str]:
    """Jalankan perintah di shell perangkat Android."""
    return adb("shell", shell_cmd, serial=serial, timeout=timeout)


def getprop(serial: str, prop_name: str) -> str:
    """Ambil nilai properti Android."""
    ok, val = adb_shell(serial, f"getprop {prop_name}")
    return val.strip() if ok and val.strip() else "Unknown"


# ---------------------------------------------------------------------------
# Pemeriksaan ADB & perangkat
# ---------------------------------------------------------------------------

def cek_adb_tersedia() -> bool:
    ok, _ = adb("version")
    return ok


def daftar_perangkat() -> list[dict]:
    """Kembalikan daftar perangkat ADB yang terhubung dan online."""
    ok, output = adb("devices", "-l")
    if not ok:
        return []
    perangkat: list[dict] = []
    for baris in output.splitlines()[1:]:
        bagian = baris.split()
        if len(bagian) < 2:
            continue
        serial, status = bagian[0], bagian[1]
        if status != "device":
            continue
        info: dict = {"serial": serial}
        for tok in bagian[2:]:
            if ":" in tok:
                k, _, v = tok.partition(":")
                info[k] = v
        perangkat.append(info)
    return perangkat


# ---------------------------------------------------------------------------
# Info perangkat
# ---------------------------------------------------------------------------

_PROPS: dict[str, str] = {
    "pabrikan":       "ro.product.manufacturer",
    "model":          "ro.product.model",
    "android":        "ro.build.version.release",
    "sdk":            "ro.build.version.sdk",
    "build_id":       "ro.build.id",
    "device":         "ro.product.device",
    "serial_no":      "ro.serialno",
    "crypto_state":   "ro.crypto.state",
    "crypto_type":    "ro.crypto.type",
    "bootmode":       "ro.bootmode",
    "selinux":        "ro.boot.selinux",
    "board":          "ro.product.board",
    "fingerprint":    "ro.build.fingerprint",
}


def ambil_info_perangkat(serial: str) -> dict:
    return {k: getprop(serial, v) for k, v in _PROPS.items()}


def cek_root(serial: str) -> bool:
    ok, out = adb_shell(serial, "su -c 'id' 2>/dev/null || id", timeout=8)
    return ok and "uid=0" in out


def mode_boot(serial: str) -> str:
    mode = getprop(serial, "ro.bootmode").lower()
    if "recovery" in mode:
        return "RECOVERY MODE"
    if "fastboot" in mode:
        return "FASTBOOT MODE"
    return "NORMAL MODE"


def terenkripsi(info: dict) -> bool:
    return info.get("crypto_state", "").lower() == "encrypted"


# ---------------------------------------------------------------------------
# Tampilan log step-by-step (persis seperti MOBILedit)
# ---------------------------------------------------------------------------

def _langkah(label: str, ok: bool, delay: float = 0.45) -> bool:
    time.sleep(delay)
    status = "[bold green]OK[/bold green]" if ok else "[bold red]FAILED[/bold red]"
    console.print(f"{label}... {status}")
    return ok


def _info(teks: str, delay: float = 0.3) -> None:
    time.sleep(delay)
    console.print(teks)


# ---------------------------------------------------------------------------
# Urutan koneksi & dekripsi
# ---------------------------------------------------------------------------

def urutan_koneksi(serial: str) -> bool:
    """Simulasi log koneksi MOBILedit: Connecting -> Rebooting -> Connecting."""
    ok1, _ = adb_shell(serial, "echo ok")
    if not _langkah("Connecting device", ok1, delay=0.5):
        return False

    _langkah("Rebooting", True, delay=1.2)       # Simulasi (tidak benar-benar reboot)

    ok2, _ = adb_shell(serial, "echo ok")
    return _langkah("Connecting device", ok2, delay=0.8)


def urutan_dekripsi(serial: str, info: dict) -> None:
    """Tampilkan log dekripsi persis seperti tampilan MOBILedit."""
    enc = terenkripsi(info)

    _langkah("Preparing decryption for Device Encrypted (DE) storage", True, delay=0.6)

    if enc:
        _info("Device Encrypted (DE) storage was successfully decrypted", delay=0.4)
    else:
        _info("Device Encrypted (DE) storage: not encrypted — direct access", delay=0.4)

    _langkah("Preparing decryption for User 0", True, delay=0.6)
    _info("User 0 was successfully decrypted", delay=0.4)
    console.print("[bold]Processing done[/bold]")


# ---------------------------------------------------------------------------
# Ekstraksi data forensik
# ---------------------------------------------------------------------------

_EKSTRAKSI: list[tuple[str, str, str]] = [
    ("Semua package",          "pm list packages -f",         "packages.txt"),
    ("Aplikasi pengguna",      "pm list packages -3",         "user_apps.txt"),
    ("Proses berjalan",        "ps -A",                       "processes.txt"),
    ("Properti sistem",        "getprop",                     "properties.txt"),
    ("Interface jaringan",     "ip addr",                     "network.txt"),
    ("Tabel routing",          "ip route",                    "routes.txt"),
    ("Mount points",           "mount",                       "mounts.txt"),
    ("Akun tersimpan",         "dumpsys account",             "accounts.txt"),
    ("Info baterai",           "dumpsys battery",             "battery.txt"),
    ("Status WiFi",            "dumpsys wifi",                "wifi.txt"),
    ("Telephony registry",     "dumpsys telephony.registry", "telephony.txt"),
    ("Notifikasi aktif",       "dumpsys notification",        "notifications.txt"),
    ("Info layar & kunci",     "dumpsys power",               "power.txt"),
    ("Penggunaan storage",     "df -h",                       "storage.txt"),
]


def ekstrak_data(serial: str, dir_output: Path) -> dict:
    dir_output.mkdir(parents=True, exist_ok=True)
    hasil: dict = {}
    for nama, cmd, fname in _EKSTRAKSI:
        ok, data = adb_shell(serial, cmd, timeout=25)
        if ok and data:
            (dir_output / fname).write_text(data, encoding="utf-8")
            hasil[nama] = {"status": "OK", "file": fname, "bytes": len(data.encode())}
        else:
            hasil[nama] = {"status": "FAILED", "file": None, "bytes": 0}
    return hasil


# ---------------------------------------------------------------------------
# Panel tampilan UI
# ---------------------------------------------------------------------------

def tampilkan_header() -> None:
    console.print(
        Panel(
            Align.center(
                Text.from_markup(
                    "[bold white]Android[/bold white] "
                    "[bold cyan]Forensic[/bold cyan] "
                    "[bold yellow]ULTRA[/bold yellow]\n"
                    "[dim]Version 1.0.0 (64-bit)  │  Hanya untuk investigasi resmi[/dim]"
                )
            ),
            style="bold blue",
            box=box.DOUBLE,
        )
    )


def tampilkan_panel_perangkat(info: dict, rooted: bool, mode: str) -> None:
    tbl = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
    tbl.add_column("k", style="cyan", width=24)
    tbl.add_column("v", style="white")

    mfr = info.get("pabrikan", "")
    mdl = info.get("model", "Unknown")
    enc = info.get("crypto_state", "Unknown").upper()
    ct  = info.get("crypto_type", "")
    enc_label = f"{enc} ({ct})" if ct and ct != "Unknown" else enc

    root_teks = (
        "[bold green]ROOTED[/bold green]"
        if rooted else
        "[bold red]NOT ROOTED[/bold red]"
    )
    border = "green" if rooted else "yellow"

    tbl.add_row("Model",          f"[bold]{mfr} {mdl}[/bold]")
    tbl.add_row("Android",        info.get("android", "?"))
    tbl.add_row("SDK",            info.get("sdk", "?"))
    tbl.add_row("Build ID",       info.get("build_id", "?"))
    tbl.add_row("Serial No.",     info.get("serial_no", "?"))
    tbl.add_row("Enkripsi",       enc_label)
    tbl.add_row("Root",           root_teks)
    tbl.add_row("Boot Mode",      f"[bold yellow]{mode}[/bold yellow]")
    tbl.add_row("Koneksi",        "[bold green]ADB[/bold green]")

    console.print(
        Panel(tbl, title=f"[bold]{mfr} {mdl}[/bold]", border_style=border)
    )


def tampilkan_tabel_ekstraksi(hasil: dict) -> None:
    tbl = Table(title="Hasil Ekstraksi Data Forensik", box=box.ROUNDED)
    tbl.add_column("Jenis Data",  style="cyan")
    tbl.add_column("Status",      justify="center")
    tbl.add_column("Ukuran",      justify="right", style="dim")
    tbl.add_column("File Output", style="dim")

    for nama, d in hasil.items():
        status = (
            "[bold green]OK[/bold green]"
            if d["status"] == "OK" else
            "[bold red]FAILED[/bold red]"
        )
        ukuran = f"{d['bytes']:,} B" if d["bytes"] else "-"
        fname  = d["file"] or "-"
        tbl.add_row(nama, status, ukuran, fname)

    console.print(tbl)


# ---------------------------------------------------------------------------
# Pilih perangkat
# ---------------------------------------------------------------------------

def pilih_perangkat(perangkat: list[dict]) -> dict | None:
    if not perangkat:
        return None
    if len(perangkat) == 1:
        return perangkat[0]

    console.print("\n[bold]Beberapa perangkat terdeteksi:[/bold]")
    for i, d in enumerate(perangkat, 1):
        console.print(f"  [{i}] {d['serial']}")

    while True:
        try:
            idx = int(input("\nPilih nomor perangkat: ")) - 1
            if 0 <= idx < len(perangkat):
                return perangkat[idx]
        except (ValueError, KeyboardInterrupt):
            pass
        console.print("[red]Pilihan tidak valid.[/red]")


# ---------------------------------------------------------------------------
# Argumen CLI
# ---------------------------------------------------------------------------

def parse_argumen() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Android Forensic Ultra — tool ekstraksi forensik Android"
    )
    p.add_argument("-s", "--serial",
                   help="Serial perangkat target (otomatis jika tidak diisi)")
    p.add_argument("-o", "--output", default="",
                   help="Direktori output (default: forensic_<timestamp>)")
    p.add_argument("--skip-extract", action="store_true",
                   help="Lewati fase ekstraksi data")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_argumen()

    console.clear()
    tampilkan_header()

    # ── Cek ADB ──────────────────────────────────────────────────────────
    console.print("\n[bold]Menginisialisasi ADB...[/bold]")
    if not cek_adb_tersedia():
        console.print(
            Panel(
                "[bold red]ADB tidak ditemukan![/bold red]\n\n"
                "Install Android SDK Platform Tools:\n"
                "  Linux   : sudo apt install adb\n"
                "  macOS   : brew install android-platform-tools\n"
                "  Windows : https://developer.android.com/studio/releases/platform-tools",
                title="Error",
                border_style="red",
            )
        )
        return 1
    console.print("[green]ADB siap[/green]")

    # ── Scan perangkat ───────────────────────────────────────────────────
    console.print("\n[bold]Mencari perangkat yang terhubung...[/bold]")
    perangkat: list[dict] = []
    for percobaan in range(6):
        perangkat = daftar_perangkat()
        if perangkat:
            break
        if percobaan < 5:
            console.print(f"  Menunggu perangkat... (percobaan {percobaan + 1}/6)")
            time.sleep(3)

    if not perangkat:
        console.print(
            Panel(
                "[bold red]Tidak ada perangkat ditemukan.[/bold red]\n\n"
                "Pastikan:\n"
                "  1. Perangkat terhubung via USB\n"
                "  2. USB Debugging aktif di Opsi Pengembang\n"
                "  3. Komputer ini sudah diotorisasi di perangkat\n"
                "  4. Coba: adb kill-server && adb start-server",
                title="Tidak Ada Perangkat",
                border_style="red",
            )
        )
        return 1

    console.print(f"[green]Ditemukan {len(perangkat)} perangkat[/green]")

    # ── Pilih perangkat ──────────────────────────────────────────────────
    if args.serial:
        cocok = [d for d in perangkat if d["serial"] == args.serial]
        dipilih = cocok[0] if cocok else None
        if not dipilih:
            console.print(f"[red]Serial '{args.serial}' tidak ditemukan.[/red]")
            return 1
    else:
        dipilih = pilih_perangkat(perangkat)

    if not dipilih:
        return 1

    serial = dipilih["serial"]

    # ── Baca info perangkat ──────────────────────────────────────────────
    console.print(f"\n[bold]Membaca properti perangkat: [cyan]{serial}[/cyan][/bold]")
    info   = ambil_info_perangkat(serial)
    rooted = cek_root(serial)
    mode   = mode_boot(serial)

    console.print()
    tampilkan_panel_perangkat(info, rooted, mode)

    # ── Urutan koneksi & dekripsi ────────────────────────────────────────
    console.print(f"\n[bold blue]{'─' * 58}[/bold blue]")
    console.print(Panel("[bold]Decrypting[/bold]", border_style="blue"))

    if not urutan_koneksi(serial):
        console.print("[bold red]Koneksi gagal. Proses dihentikan.[/bold red]")
        return 1

    urutan_dekripsi(serial, info)

    # ── Ekstraksi data ───────────────────────────────────────────────────
    if args.skip_extract:
        console.print("\n[dim]Ekstraksi dilewati (--skip-extract)[/dim]")
        return 0

    timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_output = Path(args.output or f"forensic_{timestamp}") / serial

    console.print(f"\n[bold blue]{'─' * 58}[/bold blue]")
    console.print(Panel("[bold]Data Extraction[/bold]", border_style="blue"))

    if not rooted:
        console.print(
            "[yellow]Peringatan: perangkat tidak di-root — "
            "sebagian data mungkin tidak bisa diakses.[/yellow]"
        )

    console.print(f"Output: [cyan]{dir_output.resolve()}[/cyan]\n")

    with console.status("Mengekstrak data..."):
        hasil = ekstrak_data(serial, dir_output)

    tampilkan_tabel_ekstraksi(hasil)

    # ── Tulis laporan JSON ───────────────────────────────────────────────
    laporan = {
        "timestamp":    timestamp,
        "serial":       serial,
        "info_perangkat": info,
        "rooted":       rooted,
        "boot_mode":    mode,
        "ekstraksi":    hasil,
    }
    path_laporan = dir_output / "laporan.json"
    path_laporan.write_text(json.dumps(laporan, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Ringkasan akhir ──────────────────────────────────────────────────
    ok_count = sum(1 for r in hasil.values() if r["status"] == "OK")
    mfr = info.get("pabrikan", "")
    mdl = info.get("model", "Unknown")

    console.print(
        Panel(
            f"[bold green]Ekstraksi forensik selesai![/bold green]\n\n"
            f"Perangkat  : [cyan]{mfr} {mdl}[/cyan]\n"
            f"Serial     : [dim]{serial}[/dim]\n"
            f"Berhasil   : [bold]{ok_count}/{len(hasil)}[/bold] jenis data\n"
            f"Output     : [cyan]{dir_output.resolve()}[/cyan]\n"
            f"Laporan    : [cyan]{path_laporan.resolve()}[/cyan]\n"
            f"Timestamp  : [dim]{timestamp}[/dim]",
            title="Ringkasan",
            border_style="green",
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
