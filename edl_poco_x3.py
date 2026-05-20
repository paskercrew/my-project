#!/usr/bin/env python3
"""
EDL Tool - Xiaomi Poco X3 NFC
Chipset : Qualcomm Snapdragon 732G (SM7150-AC)
Codename: surya / karna
EDL Mode: USB PID 0x9008 (Qualcomm HS-USB QDLoader 9008)

Fitur:
  - Deteksi EDL mode (9008)
  - Masuk EDL via ADB / Fastboot / Test Point
  - Baca info perangkat via EDL
  - Dump partisi (userdata, persist, misc)
  - Hapus FRP via EDL
  - Tanpa USB Debugging!

Cara masuk EDL Poco X3 NFC:
  1. ADB  : adb reboot edl
  2. Fastboot: fastboot oem edl
  3. Test Point: short TP5 ke ground saat sambung USB (lihat diagram)
  4. Volume- + sambung USB (beberapa unit)

Firehose programmer diperlukan untuk operasi partisi:
  - File: prog_firehose_ddr.elf  (dari ROM MIUI surya)
  - Ekstrak dari: firmware_surya_*.zip -> images/prog_firehose_ddr.elf
"""

import subprocess
import sys
import os
import time
import json
import argparse
from pathlib import Path
from datetime import datetime

# Auto-install dependensi
for pkg, pip_name in [
    ("rich",       "rich"),
    ("serial",     "pyserial"),
]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pip_name], check=True)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.align import Align
from rich import box

console = Console()

# ---------------------------------------------------------------------------
# Konstanta Poco X3 NFC
# ---------------------------------------------------------------------------

DEVICE_INFO = {
    "name":      "Xiaomi Poco X3 NFC",
    "codename":  ["surya", "karna"],
    "chipset":   "Qualcomm Snapdragon 732G (SM7150-AC)",
    "cpu_arch":  "ARM64 (Kryo 470)",
    "storage":   "UFS 2.1",
    "edl_pid":   "0x9008",
    "edl_vid":   "0x05C6",
    "programmer": "prog_firehose_ddr.elf",
    "firmware_codename": "surya",
}

# Partisi penting Poco X3 NFC
PARTISI = {
    "userdata":   {"desc": "Data pengguna (foto, app, dll)",      "size_approx": "besar"},
    "persist":    {"desc": "Data persist (Wi-Fi MAC, DRM keys)",  "size_approx": "~30MB"},
    "misc":       {"desc": "Misc flags (FRP, bootmode)",          "size_approx": "~4MB"},
    "frp":        {"desc": "Factory Reset Protection",            "size_approx": "~1MB"},
    "abl":        {"desc": "Android Bootloader",                  "size_approx": "~5MB"},
    "boot":       {"desc": "Kernel + ramdisk",                    "size_approx": "~100MB"},
    "recovery":   {"desc": "Recovery partition",                  "size_approx": "~100MB"},
    "system":     {"desc": "System MIUI",                         "size_approx": "~3GB"},
    "vendor":     {"desc": "Vendor partition",                    "size_approx": "~1GB"},
    "modem":      {"desc": "Baseband firmware",                   "size_approx": "~200MB"},
}

# ---------------------------------------------------------------------------
# Deteksi USB (tanpa library khusus)
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


def cek_adb() -> bool:
    ok, _ = _run(["adb", "version"])
    return ok

def cek_fastboot() -> bool:
    ok, _ = _run(["fastboot", "--version"])
    return ok

def cek_edlclient() -> bool:
    ok, _ = _run([sys.executable, "-m", "edlclient", "--help"])
    return ok


def daftar_adb() -> list[str]:
    ok, out = _run(["adb", "devices"])
    if not ok: return []
    return [b.split()[0] for b in out.splitlines()[1:]
            if len(b.split()) >= 2 and b.split()[1] == "device"]


def daftar_fastboot() -> list[str]:
    ok, out = _run(["fastboot", "devices"])
    if not ok: return []
    return [b.split()[0] for b in out.splitlines()
            if b.strip() and "fastboot" in b]


def deteksi_edl_mode_windows() -> bool:
    """Cek apakah ada device 9008 di Windows via mode USB."""
    ok, out = _run(["pnputil", "/enum-devices", "/connected"], timeout=10)
    if ok and ("9008" in out or "QDLoader" in out.lower() or "qdloader" in out.lower()):
        return True
    # Coba via wmic
    ok2, out2 = _run(
        ["wmic", "path", "Win32_USBHub", "where",
         "DeviceID like '%VID_05C6%PID_9008%'", "get", "DeviceID"],
        timeout=10)
    return ok2 and "VID_05C6" in out2


def deteksi_edl_mode_linux() -> bool:
    """Cek device 9008 di Linux via lsusb."""
    ok, out = _run(["lsusb"], timeout=10)
    return ok and ("05c6:9008" in out.lower() or "qdloader" in out.lower())


def deteksi_edl() -> bool:
    if sys.platform == "win32":
        return deteksi_edl_mode_windows()
    return deteksi_edl_mode_linux()


# ---------------------------------------------------------------------------
# Masuk EDL
# ---------------------------------------------------------------------------

def masuk_edl_via_adb(serial: str = "") -> bool:
    cmd = ["adb"]
    if serial: cmd += ["-s", serial]
    cmd += ["reboot", "edl"]
    ok, _ = _run(cmd, timeout=10)
    if ok:
        console.print("[green]Perintah EDL dikirim via ADB[/green]")
        console.print("[dim]Menunggu perangkat masuk EDL mode...[/dim]")
        time.sleep(5)
    return ok


def masuk_edl_via_fastboot(serial: str = "") -> bool:
    cmd = ["fastboot"]
    if serial: cmd += ["-s", serial]
    cmd += ["oem", "edl"]
    ok, _ = _run(cmd, timeout=10)
    if ok:
        console.print("[green]Perintah EDL dikirim via Fastboot[/green]")
        time.sleep(5)
    return ok


# ---------------------------------------------------------------------------
# Operasi EDL via edlclient
# ---------------------------------------------------------------------------

def edl_info(programmer: str = "") -> tuple[bool, str]:
    """Baca info perangkat via EDL (firehose)."""
    cmd = [sys.executable, "-m", "edlclient", "printgpt"]
    if programmer:
        cmd += ["--loader", programmer]
    return _run(cmd, timeout=30)


def edl_dump_partisi(nama: str, output: Path,
                     programmer: str = "") -> tuple[bool, str]:
    """Dump satu partisi ke file."""
    out_file = output / f"{nama}.bin"
    cmd = [sys.executable, "-m", "edlclient",
           "rf", nama, str(out_file)]
    if programmer:
        cmd += ["--loader", programmer]
    return _run(cmd, timeout=600)


def edl_hapus_frp(programmer: str = "") -> tuple[bool, str]:
    """Hapus partisi FRP (erase)."""
    cmd = [sys.executable, "-m", "edlclient",
           "e", "frp"]
    if programmer:
        cmd += ["--loader", programmer]
    return _run(cmd, timeout=60)


def edl_hapus_misc(programmer: str = "") -> tuple[bool, str]:
    """Hapus partisi misc (reset flags bootmode, FRP)."""
    cmd = [sys.executable, "-m", "edlclient",
           "e", "misc"]
    if programmer:
        cmd += ["--loader", programmer]
    return _run(cmd, timeout=60)


# ---------------------------------------------------------------------------
# Metode manual FRP via ADB (tanpa EDL)
# ---------------------------------------------------------------------------

_FRP_ADB_CMDS = [
    ("setup_complete",
     "content insert --uri content://settings/secure "
     "--bind name:s:user_setup_complete --bind value:s:1"),
    ("device_provisioned",
     "content insert --uri content://settings/global "
     "--bind name:s:device_provisioned --bind value:s:1"),
    ("clear_gsf",   "pm clear com.google.android.gsf"),
    ("clear_gms",   "pm clear com.google.android.gms"),
    ("clear_xiaomi","pm clear com.xiaomi.account 2>/dev/null"),
    ("clear_setup", "pm clear com.miui.setupwizard 2>/dev/null || "
                    "pm clear com.google.android.setupwizard"),
]


def frp_via_adb(serial: str) -> list[tuple[str, bool]]:
    hasil = []
    for nama, cmd in _FRP_ADB_CMDS:
        full = ["adb"]
        if serial: full += ["-s", serial]
        full += ["shell", cmd]
        ok, _ = _run(full, timeout=15)
        hasil.append((nama, ok))
    return hasil


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def tampilkan_header() -> None:
    console.print(
        Panel(
            Align.center(Text.from_markup(
                "[bold cyan]Poco X3 NFC[/bold cyan] "
                "[bold white]EDL Tool[/bold white]\n"
                "[dim]Snapdragon 732G (SM7150-AC) | surya / karna[/dim]\n"
                "[dim]USB PID: 0x9008 | Qualcomm EDL Protocol[/dim]"
            )),
            style="bold blue", box=box.DOUBLE,
        )
    )


def tampilkan_info_device() -> None:
    tbl = Table(show_header=False, box=box.SIMPLE, padding=(0,1))
    tbl.add_column("k", style="cyan", width=20)
    tbl.add_column("v", style="white")
    for k, v in DEVICE_INFO.items():
        if isinstance(v, list): v = " / ".join(v)
        tbl.add_row(k, str(v))
    console.print(Panel(tbl, title="[bold]Info Perangkat[/bold]",
                        border_style="blue"))


def panduan_test_point() -> None:
    console.print(Panel(
        "[bold yellow]Cara masuk EDL via Test Point (Poco X3 NFC):[/bold yellow]\n\n"
        "1. Matikan HP\n"
        "2. Buka casing belakang\n"
        "3. Cari pad TP5 di PCB (dekat konektor baterai)\n"
        "4. Short TP5 ke ground menggunakan pinset/kabel\n"
        "5. Sambungkan USB ke PC (tetap short)\n"
        "6. Lepas short setelah PC deteksi device 9008\n\n"
        "[dim]PC akan mendeteksi: 'Qualcomm HS-USB QDLoader 9008'[/dim]\n"
        "[dim]Di Device Manager Windows: Ports (COM & LPT)[/dim]",
        title="[bold]Test Point Guide[/bold]",
        border_style="yellow",
    ))


def panduan_edl_software() -> None:
    console.print(Panel(
        "[bold green]Cara masuk EDL via Software (Poco X3 NFC):[/bold green]\n\n"
        "[bold]Metode 1 - ADB (USB Debugging aktif):[/bold]\n"
        "  adb reboot edl\n\n"
        "[bold]Metode 2 - Fastboot (BL Unlock):[/bold]\n"
        "  fastboot oem edl\n\n"
        "[bold]Metode 3 - MiFlash / QFIL:[/bold]\n"
        "  Buka MiFlash -> klik 'Flash'\n"
        "  Pilih programmer: prog_firehose_ddr.elf\n\n"
        "[bold]Metode 4 - Volume Button:[/bold]\n"
        "  HP mati + tahan Volume- + sambung USB\n"
        "  (tidak selalu berhasil tanpa test point)\n",
        title="[bold]EDL via Software[/bold]",
        border_style="green",
    ))


def tampilkan_partisi() -> None:
    tbl = Table(title="Partisi Penting Poco X3 NFC", box=box.ROUNDED)
    tbl.add_column("Partisi",  style="cyan")
    tbl.add_column("Keterangan", style="white")
    tbl.add_column("Ukuran",   style="dim")
    for nama, info in PARTISI.items():
        tbl.add_row(nama, info["desc"], info["size_approx"])
    console.print(tbl)


def tampilkan_hasil_frp(hasil: list[tuple[str, bool]]) -> None:
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
    tbl.add_column("m", style="dim", width=28)
    tbl.add_column("s", justify="center")
    for nama, ok in hasil:
        tbl.add_row(nama,
                    "[green]OK[/green]" if ok else "[dim]SKIP[/dim]")
    console.print(tbl)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="EDL Tool - Xiaomi Poco X3 NFC (SM7150)"
    )
    sub = p.add_subparsers(dest="cmd")

    # info
    sub.add_parser("info",
        help="Tampilkan info Poco X3 NFC + panduan EDL")

    # masuk-edl
    me = sub.add_parser("masuk-edl",
        help="Masuk EDL mode via ADB atau Fastboot")
    me.add_argument("-s", "--serial", default="", help="Serial ADB")
    me.add_argument("--via", choices=["adb","fastboot"], default="adb")

    # cek-edl
    sub.add_parser("cek-edl",
        help="Cek apakah perangkat sudah di EDL mode (9008)")

    # hapus-frp
    hf = sub.add_parser("hapus-frp",
        help="Hapus FRP Poco X3 NFC")
    hf.add_argument("-s", "--serial", default="")
    hf.add_argument("--edl",          action="store_true",
        help="Hapus via EDL (partisi frp+misc) -- butuh edlclient")
    hf.add_argument("--programmer",   default="",
        help="Path ke prog_firehose_ddr.elf")

    # dump
    dm = sub.add_parser("dump",
        help="Dump partisi via EDL -- butuh edlclient + programmer")
    dm.add_argument("partisi",
        nargs="+", choices=list(PARTISI.keys()),
        help="Nama partisi yang akan di-dump")
    dm.add_argument("-o", "--output", default="edl_dump")
    dm.add_argument("--programmer", default="",
        help="Path ke prog_firehose_ddr.elf")

    # partisi
    sub.add_parser("partisi",
        help="Tampilkan daftar partisi penting Poco X3 NFC")

    # test-point
    sub.add_parser("test-point",
        help="Tampilkan panduan test point Poco X3 NFC")

    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    console.clear()
    tampilkan_header()

    if not args.cmd or args.cmd == "info":
        tampilkan_info_device()
        console.print()
        panduan_edl_software()
        console.print()
        panduan_test_point()
        return 0

    # ---- cek-edl ----
    if args.cmd == "cek-edl":
        console.print("\n[bold]Memeriksa EDL mode (USB 0x9008)...[/bold]")
        ada = deteksi_edl()
        if ada:
            console.print(Panel(
                "[bold green]EDL mode terdeteksi![/bold green]\n"
                "Perangkat siap menerima perintah firehose.",
                border_style="green"))
        else:
            console.print(Panel(
                "[bold red]EDL mode tidak terdeteksi.[/bold red]\n"
                "Coba masuk EDL dulu:\n"
                "  adb reboot edl\n"
                "  fastboot oem edl\n"
                "  atau gunakan test point.",
                border_style="red"))
        return 0 if ada else 1

    # ---- masuk-edl ----
    if args.cmd == "masuk-edl":
        console.print(f"\n[bold]Masuk EDL via {args.via.upper()}...[/bold]")
        if args.via == "adb":
            if not cek_adb():
                console.print("[red]ADB tidak ditemukan.[/red]")
                return 1
            ok = masuk_edl_via_adb(args.serial)
        else:
            if not cek_fastboot():
                console.print("[red]Fastboot tidak ditemukan.[/red]")
                return 1
            ok = masuk_edl_via_fastboot(args.serial)

        if ok:
            console.print("[dim]Tunggu beberapa detik, lalu cek dengan:[/dim]")
            console.print("  [cyan]python edl_poco_x3.py cek-edl[/cyan]")
        return 0 if ok else 1

    # ---- test-point ----
    if args.cmd == "test-point":
        panduan_test_point()
        return 0

    # ---- partisi ----
    if args.cmd == "partisi":
        tampilkan_partisi()
        return 0

    # ---- hapus-frp ----
    if args.cmd == "hapus-frp":
        console.print("\n[bold blue]Hapus FRP - Poco X3 NFC[/bold blue]\n")

        if args.edl:
            # Via EDL
            if not cek_edlclient():
                console.print(Panel(
                    "[red]edlclient tidak terinstall.[/red]\n"
                    "Install: pip install edlclient",
                    border_style="red"))
                return 1
            if not deteksi_edl():
                console.print("[red]EDL mode tidak terdeteksi. Masuk EDL dulu.[/red]")
                return 1
            console.print("[green]EDL mode aktif. Menghapus partisi FRP + misc...[/green]")
            ok1, out1 = edl_hapus_frp(args.programmer)
            console.print(f"Erase FRP  : ",  end="")
            console.print("[green]OK[/green]" if ok1 else f"[red]FAILED: {out1[:60]}[/red]")
            ok2, out2 = edl_hapus_misc(args.programmer)
            console.print(f"Erase misc : ", end="")
            console.print("[green]OK[/green]" if ok2 else f"[red]FAILED: {out2[:60]}[/red]")
            if ok1 or ok2:
                console.print(Panel(
                    "[green]FRP berhasil dihapus via EDL![/green]\n"
                    "Restart HP untuk menyelesaikan proses.",
                    border_style="green"))
            return 0
        else:
            # Via ADB
            if not cek_adb():
                console.print("[red]ADB tidak ditemukan.[/red]")
                return 1
            serials = daftar_adb()
            if not serials:
                console.print("[red]Tidak ada perangkat ADB.[/red]")
                return 1
            serial = args.serial or serials[0]
            console.print(f"[cyan]Perangkat: {serial}[/cyan]")
            console.print("[bold]Menghapus FRP via ADB...[/bold]\n")
            hasil = frp_via_adb(serial)
            tampilkan_hasil_frp(hasil)
            ok_n = sum(1 for _, ok in hasil if ok)
            if ok_n > 0:
                console.print(f"\n[green]Selesai: {ok_n}/{len(hasil)} metode berhasil[/green]")
            else:
                console.print("\n[red]Semua metode gagal. Coba gunakan --edl[/red]")
            return 0

    # ---- dump ----
    if args.cmd == "dump":
        if not cek_edlclient():
            console.print(Panel(
                "[red]edlclient tidak terinstall.[/red]\n\n"
                "Install:\n  pip install edlclient\n\n"
                "Atau clone dari GitHub:\n"
                "  git clone https://github.com/bkerler/edlclient",
                border_style="red"))
            return 1

        if not deteksi_edl():
            console.print("[red]EDL mode tidak terdeteksi.[/red]")
            console.print("[dim]Masuk EDL dulu: python edl_poco_x3.py masuk-edl[/dim]")
            return 1

        out_dir = Path(args.output) / datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir.mkdir(parents=True, exist_ok=True)

        programmer = args.programmer
        if programmer and not Path(programmer).exists():
            console.print(f"[red]Programmer tidak ditemukan: {programmer}[/red]")
            return 1

        tbl = Table(title="Hasil Dump Partisi", box=box.ROUNDED)
        tbl.add_column("Partisi",  style="cyan")
        tbl.add_column("Status",   justify="center")
        tbl.add_column("Output",   style="dim")

        for nama in args.partisi:
            console.print(f"\nDump {nama}...", end="")
            ok, out = edl_dump_partisi(nama, out_dir, programmer)
            status = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
            fpath  = str(out_dir / f"{nama}.bin") if ok else out[:40]
            tbl.add_row(nama, status, fpath)
            console.print(" " + ("OK" if ok else f"FAILED: {out[:40]}"))

        console.print()
        console.print(tbl)
        console.print(f"\n[cyan]Output: {out_dir.resolve()}[/cyan]")
        return 0

    p = argparse.ArgumentParser()
    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
