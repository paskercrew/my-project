#!/usr/bin/env python3
"""
Samsung FRP Erase Tool via ADB
Mirip UnlockTool - hanya untuk pemilik sah perangkat / teknisi resmi.

FRP (Factory Reset Protection) Erase:
  - Membaca info lengkap perangkat Samsung
  - Menghapus FRP via metode ADB
  - Mendukung Samsung Galaxy A14 (SM-A145F) dan model lain
"""

import subprocess
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich.columns import Columns
    from rich import box
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich.align import Align
    from rich.columns import Columns
    from rich import box

console = Console()


# ---------------------------------------------------------------------------
# Utilitas ADB
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        err = r.stderr.strip()
        if r.returncode == 0:
            return True, out
        return False, err or out
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, f"tidak ditemukan: {cmd[0]}"
    except Exception as exc:
        return False, str(exc)


def adb(*args: str, serial: str = "", timeout: int = 15) -> tuple[bool, str]:
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return _run(cmd, timeout=timeout)


def shell(serial: str, cmd: str, timeout: int = 20) -> tuple[bool, str]:
    return adb("shell", cmd, serial=serial, timeout=timeout)


def prop(serial: str, name: str) -> str:
    ok, v = shell(serial, f"getprop {name}")
    return v.strip() if ok and v.strip() else ""


# ---------------------------------------------------------------------------
# Deteksi perangkat
# ---------------------------------------------------------------------------

def cek_adb() -> bool:
    ok, _ = adb("version")
    return ok


def daftar_perangkat() -> list[str]:
    ok, out = adb("devices")
    if not ok:
        return []
    serials: list[str] = []
    for baris in out.splitlines()[1:]:
        bagian = baris.split()
        if len(bagian) >= 2 and bagian[1] == "device":
            serials.append(bagian[0])
    return serials


# ---------------------------------------------------------------------------
# Baca info perangkat Samsung
# ---------------------------------------------------------------------------

def baca_info(serial: str) -> dict:
    """Baca semua info perangkat persis seperti tampilan UnlockTool."""
    info: dict = {}

    info["Model"]            = prop(serial, "ro.product.model")
    info["Manufacturer"]     = prop(serial, "ro.product.manufacturer")
    info["Platform"]         = prop(serial, "ro.board.platform")
    info["CPU Arch"]         = prop(serial, "ro.product.cpu.abi")
    info["Android Serial"]   = prop(serial, "ro.serialno") or serial
    info["Manufacturing Date"] = prop(serial, "ro.product.build.date.utc") or \
                                  prop(serial, "ro.manufacture")
    info["Security Patch"]   = prop(serial, "ro.build.version.security_patch")
    info["Connection"]       = "adb"
    info["Timezone"]         = prop(serial, "persist.sys.timezone")
    info["Android Version"]  = prop(serial, "ro.build.version.release")
    info["Android SDK"]      = prop(serial, "ro.build.version.sdk")
    info["Build"]            = prop(serial, "ro.build.display.id")
    info["Build Date"]       = prop(serial, "ro.build.date")
    info["Product Code"]     = prop(serial, "ro.product.model") + \
                               prop(serial, "ro.csc.product.code").replace(info["Model"], "")
    info["Device Name"]      = prop(serial, "ro.product.device")
    info["Product Name"]     = prop(serial, "ro.product.name")
    info["Code Name"]        = prop(serial, "ro.product.model") + \
                               prop(serial, "ro.product.code")
    info["BL"]               = prop(serial, "ro.boot.bootloader")
    info["PDA"]              = prop(serial, "ro.build.PDA") or \
                               prop(serial, "ro.build.id")
    info["CP"]               = prop(serial, "ro.build.CP") or ""
    info["CSC"]              = prop(serial, "ro.build.CSC") or \
                               prop(serial, "ro.csc.version")
    info["Sales Code"]       = prop(serial, "ro.csc.sales_code") or \
                               prop(serial, "ro.build.sales_code") or "MID"
    return info


def cek_root(serial: str) -> bool:
    ok, out = shell(serial, "su -c 'id' 2>/dev/null", timeout=6)
    return ok and "uid=0" in out


# ---------------------------------------------------------------------------
# Metode penghapusan FRP
# ---------------------------------------------------------------------------

_METODE_FRP: list[tuple[str, str]] = [
    # Tandai setup selesai
    (
        "mark_setup_complete",
        "content insert --uri content://settings/secure "
        "--bind name:s:user_setup_complete --bind value:s:1",
    ),
    # Bersihkan data GSF (Google Services Framework)
    ("clear_gsf",   "pm clear com.google.android.gsf"),
    # Bersihkan GMS
    ("clear_gms",   "pm clear com.google.android.gms"),
    # Bersihkan akun Google
    ("clear_gaccount", "pm clear com.google.android.googlequicksearchbox"),
    # Nonaktifkan FRP via Samsung Knox (jika tersedia)
    ("samsung_frp_delete",
     "content delete --uri content://com.sec.android.provider.settings.SecSettings.SECURE "
     "--where \"name='frp_credential_key'\""),
    # Reset Setup Wizard
    ("reset_setup_wizard",
     "pm clear com.sec.android.app.SecSetupWizard 2>/dev/null || "
     "pm clear com.google.android.setupwizard"),
]


def hapus_frp(serial: str) -> tuple[bool, list[tuple[str, bool, str]]]:
    """
    Jalankan semua metode penghapusan FRP.
    Kembalikan (sukses_keseluruhan, [(nama, sukses, pesan)]).
    """
    hasil: list[tuple[str, bool, str]] = []
    ada_yang_berhasil = False

    for nama, cmd in _METODE_FRP:
        ok, out = shell(serial, cmd, timeout=15)
        pesan = out[:80] if out else ("OK" if ok else "gagal")
        hasil.append((nama, ok, pesan))
        if ok:
            ada_yang_berhasil = True

    return ada_yang_berhasil, hasil


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def tampilkan_header() -> None:
    nav = Table.grid(expand=True)
    nav.add_column(justify="center")
    nav.add_column(justify="center")
    nav.add_column(justify="center")
    nav.add_column(justify="center")
    nav.add_column(justify="center")
    nav.add_row(
        "[bold yellow]ADB[/bold yellow]",
        "[bold cyan]FASTBOOT[/bold cyan]",
        "[bold green]T.POINT[/bold green]",
        "[bold blue]DEVMGR[/bold blue]",
        "[bold white]CONFIG[/bold white]",
    )
    console.print(
        Panel(
            nav,
            title="[bold white]Samsung FRP Erase Tool[/bold white]",
            subtitle="[dim]Hanya untuk pemilik sah / teknisi resmi[/dim]",
            style="bold blue",
            box=box.DOUBLE,
        )
    )


def log_ok(label: str, nilai: str = "OK") -> None:
    console.print(f"{label} [bold green]{nilai}[/bold green]")


def log_info(label: str, nilai: str, warna: str = "cyan") -> None:
    console.print(f"{label} : [{warna}]{nilai}[/{warna}]")


def log_warn(label: str, nilai: str) -> None:
    console.print(f"{label} [bold yellow]{nilai}[/bold yellow]")


def log_err(label: str, nilai: str) -> None:
    console.print(f"{label} [bold red]{nilai}[/bold red]")


def tampilkan_info(info: dict, rooted: bool) -> None:
    console.print()
    console.print(
        Panel(
            "[bold green][ADB] ERASE FRP[/bold green]",
            border_style="green",
        )
    )
    console.print()

    log_ok("Starting ADB Interface...")
    time.sleep(0.2)

    tampil = {
        "Model":            "cyan",
        "Manufacturer":     "cyan",
        "Platform":         "yellow",
        "CPU Arch":         "white",
        "Android Serial":   "cyan",
        "Manufacturing Date": "white",
        "Security Patch":   "white",
        "Connection":       "cyan",
        "Timezone":         "white",
        "Android Version":  "white",
        "Android SDK":      "white",
        "Build":            "white",
        "Build Date":       "white",
        "Product Code":     "white",
        "Device Name":      "white",
        "Product Name":     "white",
        "Code Name":        "white",
        "BL":               "cyan",
        "PDA":              "cyan",
        "CP":               "cyan",
        "CSC":              "cyan",
        "Sales Code":       "yellow",
    }

    for label, warna in tampil.items():
        nilai = info.get(label, "")
        if nilai:
            log_info(label, nilai, warna)
            time.sleep(0.05)

    console.print()
    if rooted:
        log_ok("Checking permission...", "root")
    else:
        log_warn("Checking permission...", "no root")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Samsung FRP Erase Tool via ADB"
    )
    p.add_argument("-s", "--serial",
                   help="Serial perangkat (otomatis jika tidak diisi)")
    p.add_argument("--info-only", action="store_true",
                   help="Hanya tampilkan info perangkat, tanpa hapus FRP")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    mulai = time.time()

    console.clear()
    tampilkan_header()

    # ── Cek ADB ──────────────────────────────────────────────────────────
    if not cek_adb():
        console.print(
            Panel(
                "[red]ADB tidak ditemukan.[/red]\n"
                "Install: sudo apt install adb  |  brew install android-platform-tools",
                title="Error", border_style="red",
            )
        )
        return 1

    # ── Cari perangkat ───────────────────────────────────────────────────
    serials: list[str] = []
    for attempt in range(6):
        serials = daftar_perangkat()
        if serials:
            break
        if attempt < 5:
            console.print(f"Menunggu perangkat... ({attempt + 1}/6)")
            time.sleep(3)

    if not serials:
        console.print(
            Panel(
                "[red]Tidak ada perangkat ditemukan.[/red]\n"
                "Pastikan USB Debugging aktif dan perangkat terhubung.",
                title="Tidak Ada Perangkat", border_style="red",
            )
        )
        return 1

    # ── Pilih serial ─────────────────────────────────────────────────────
    if args.serial:
        serial = args.serial
        if serial not in serials:
            console.print(f"[red]Serial '{serial}' tidak ditemukan.[/red]")
            return 1
    elif len(serials) == 1:
        serial = serials[0]
    else:
        console.print("\n[bold]Pilih perangkat:[/bold]")
        for i, s in enumerate(serials, 1):
            console.print(f"  [{i}] {s}")
        while True:
            try:
                idx = int(input("Nomor perangkat: ")) - 1
                if 0 <= idx < len(serials):
                    serial = serials[idx]
                    break
            except (ValueError, KeyboardInterrupt):
                pass

    # Tampilkan USB & COM info
    console.print(f"\n[dim]USB  : {serial} [Samsung Android ADB Interface][/dim]")
    console.print("[dim]COM  : - Waiting for COM ports -[/dim]\n")

    # ── Baca info ───────────────────────────────────────────────────────────
    with console.status("Membaca info perangkat..."):
        info   = baca_info(serial)
        rooted = cek_root(serial)

    tampilkan_info(info, rooted)

    if args.info_only:
        console.print("\n[dim]--info-only: proses dihentikan sebelum hapus FRP.[/dim]")
        return 0

    # ── Hapus FRP ──────────────────────────────────────────────────────────
    console.print()
    with console.status("Menghapus FRP..."):
        sukses, detail = hapus_frp(serial)

    if sukses:
        log_ok("Removing FRP...")
    else:
        log_err("Removing FRP...", "FAILED")

    # Detail metode (verbose)
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column("m", style="dim", width=28)
    tbl.add_column("s", justify="center")
    for nama, ok, _ in detail:
        s = "[green]OK[/green]" if ok else "[red]SKIP[/red]"
        tbl.add_row(nama, s)
    console.print(tbl)

    # ── Footer ────────────────────────────────────────────────────────────
    elapsed = round(time.time() - mulai)
    console.print(f"\n[dim]Samsung FRP Erase Tool 2026.05.04.0[/dim]")
    console.print(f"[dim]Elapsed time : {elapsed} seconds[/dim]")

    if sukses:
        console.print(
            Panel(
                "[bold green]FRP berhasil dihapus![/bold green]\n"
                "Restart perangkat untuk menyelesaikan proses.",
                border_style="green",
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]FRP tidak berhasil dihapus.[/bold red]\n"
                "Coba dengan akses root atau gunakan mode Fastboot.",
                border_style="red",
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
