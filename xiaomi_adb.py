#!/usr/bin/env python3
"""
Xiaomi / POCO ADB Tool
Dioptimalkan untuk Poco X3 NFC (codename: surya / karna)
Fitur:
  - Baca info lengkap perangkat Xiaomi/MIUI
  - Cek status bootloader (locked/unlocked)
  - Cek Mi Account (FRP Xiaomi)
  - Hapus Mi Account / FRP via ADB
  - Ekstraksi data forensik MIUI
Hanya untuk pemilik sah perangkat.
"""

import subprocess
import sys
import time
import json
import argparse
from datetime import datetime
from pathlib import Path

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
# Kode warna MIUI (mirip tampilan UnlockTool / XiaoMiTool)
# ---------------------------------------------------------------------------
HIJAU  = "bold green"
CYAN   = "cyan"
KUNING = "yellow"
MERAH  = "bold red"
PUTIH  = "white"
DIM    = "dim"


# ---------------------------------------------------------------------------
# Utilitas ADB dasar
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        err = r.stderr.strip()
        return (r.returncode == 0), (out if r.returncode == 0 else err or out)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, f"tidak ditemukan: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def adb(*args: str, serial: str = "", timeout: int = 15) -> tuple[bool, str]:
    cmd = ["adb"] + (["- s", serial] if serial else []) + list(args)
    # Perbaikan: flag -s harus pisah
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += list(args)
    return _run(cmd, timeout=timeout)


def shell(serial: str, cmd: str, timeout: int = 20) -> tuple[bool, str]:
    return adb("shell", cmd, serial=serial, timeout=timeout)


def prop(serial: str, key: str) -> str:
    ok, v = shell(serial, f"getprop {key}")
    return v.strip() if ok and v.strip() else ""


def fastboot(*args: str, timeout: int = 30) -> tuple[bool, str]:
    return _run(["fastboot"] + list(args), timeout=timeout)


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
    return [
        b.split()[0]
        for b in out.splitlines()[1:]
        if len(b.split()) >= 2 and b.split()[1] == "device"
    ]


# ---------------------------------------------------------------------------
# Info Xiaomi / POCO / MIUI
# ---------------------------------------------------------------------------

# Properti khusus Xiaomi/MIUI
_PROPS_XIAOMI: dict[str, str] = {
    # Identitas perangkat
    "Merek":              "ro.product.brand",
    "Model":              "ro.product.model",
    "Nama Produk":        "ro.product.name",
    "Codename":           "ro.product.device",
    "Pabrikan":           "ro.product.manufacturer",
    # Platform
    "Platform / SoC":     "ro.board.platform",
    "CPU Arch":           "ro.product.cpu.abi",
    # MIUI
    "Versi MIUI":         "ro.miui.ui.version.name",
    "Build MIUI":         "ro.miui.ui.version.code",
    "Versi Android":      "ro.build.version.release",
    "Android SDK":        "ro.build.version.sdk",
    "Build ID":           "ro.build.display.id",
    "Build Date":         "ro.build.date",
    "Security Patch":     "ro.build.version.security_patch",
    # Serial & koneksi
    "Serial":             "ro.serialno",
    "Timezone":           "persist.sys.timezone",
    # Bootloader
    "Bootloader":         "ro.boot.bootloader",
    "Versi Bootloader":   "ro.bootloader",
    # Radio / baseband
    "Baseband":           "gsm.version.baseband",
    # Region
    "Region":             "ro.miui.region",
    "Sales Region":       "ro.product.locale",
    # Fingerprint
    "Fingerprint":        "ro.build.fingerprint",
}

# Codename Poco X3 NFC yang dikenal
_POCO_X3_NFC_CODENAMES = {"surya", "karna"}


def baca_info(serial: str) -> dict:
    return {k: prop(serial, v) for k, v in _PROPS_XIAOMI.items()}


def adalah_poco_x3_nfc(info: dict) -> bool:
    codename = info.get("Codename", "").lower()
    model    = info.get("Model", "").lower()
    return (
        codename in _POCO_X3_NFC_CODENAMES
        or "surya" in model
        or "karna" in model
        or "x3" in model
    )


# ---------------------------------------------------------------------------
# Cek status penting
# ---------------------------------------------------------------------------

def cek_root(serial: str) -> bool:
    ok, out = shell(serial, "su -c 'id' 2>/dev/null", timeout=6)
    return ok and "uid=0" in out


def cek_bootloader(serial: str) -> str:
    """
    Kembalikan: 'UNLOCKED' / 'LOCKED' / 'UNKNOWN'
    Dicek via ro.boot.flash.locked dan ro.secureboot.lockstate.
    """
    locked1 = prop(serial, "ro.boot.flash.locked")
    locked2 = prop(serial, "ro.secureboot.lockstate")
    verif   = prop(serial, "ro.boot.verifiedbootstate")

    if locked1 == "0" or locked2 == "unlocked" or verif == "orange":
        return "UNLOCKED"
    if locked1 == "1" or locked2 == "locked" or verif in ("green", "yellow"):
        return "LOCKED"
    return "UNKNOWN"


def cek_mi_account(serial: str) -> tuple[bool, str]:
    """
    Cek apakah Mi Account (MIUI FRP) aktif.
    Kembalikan (aktif, email/status).
    """
    # Coba baca akun via AccountManager
    ok, out = shell(
        serial,
        "dumpsys account 2>/dev/null | grep -i 'xiaomi\\|mi.com\\|miui'",
        timeout=15,
    )
    if ok and out.strip():
        return True, out.splitlines()[0].strip()[:80]

    # Cek package Mi Account
    ok2, out2 = shell(serial, "pm path com.xiaomi.account 2>/dev/null")
    if ok2 and "package:" in out2:
        # Package ada, coba cek data
        ok3, out3 = shell(
            serial,
            "content query --uri content://com.xiaomi.account.provider/ 2>/dev/null | head -3",
            timeout=10,
        )
        if ok3 and out3.strip():
            return True, "Mi Account aktif"
        return False, "Package ada, akun tidak terdeteksi"

    return False, "Tidak ada Mi Account terdeteksi"


def cek_frp_google(serial: str) -> str:
    """Cek status FRP Google (user_setup_complete)."""
    ok, out = shell(
        serial,
        "content query --uri content://settings/secure --where \"name='user_setup_complete'\"",
        timeout=10,
    )
    if ok and "value=1" in out:
        return "SELESAI (tidak ada FRP)"
    if ok and "value=0" in out:
        return "AKTIF (setup belum selesai)"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Aksi: Hapus FRP / Mi Account
# ---------------------------------------------------------------------------

_METODE_FRP: list[tuple[str, str]] = [
    ("setup_complete",
     "content insert --uri content://settings/secure "
     "--bind name:s:user_setup_complete --bind value:s:1"),
    ("device_provisioned",
     "content insert --uri content://settings/global "
     "--bind name:s:device_provisioned --bind value:s:1"),
    ("clear_gsf",        "pm clear com.google.android.gsf"),
    ("clear_gms",        "pm clear com.google.android.gms"),
    ("clear_setupwizard","pm clear com.google.android.setupwizard 2>/dev/null || "
                         "pm clear com.miui.setupwizard"),
    ("clear_mi_account", "pm clear com.xiaomi.account 2>/dev/null"),
    ("disable_mi_frp",
     "settings put global device_provisioned 1"),
    ("am_setup_complete",
     "am broadcast -a android.intent.action.USER_INITIALIZE 2>/dev/null"),
]


def hapus_frp(serial: str) -> tuple[bool, list[tuple[str, bool]]]:
    detail: list[tuple[str, bool]] = []
    ada_sukses = False
    for nama, cmd in _METODE_FRP:
        ok, _ = shell(serial, cmd, timeout=15)
        detail.append((nama, ok))
        if ok:
            ada_sukses = True
    return ada_sukses, detail


def hapus_mi_account(serial: str) -> tuple[bool, str]:
    """Hapus data Mi Account via ADB (butuh akses ADB + mungkin root)."""
    ok1, _ = shell(serial, "pm clear com.xiaomi.account", timeout=15)
    ok2, _ = shell(serial, "pm clear com.xiaomi.micloud", timeout=10)
    ok3, _ = shell(serial, "settings delete global mi_account_name 2>/dev/null", timeout=10)
    if ok1 or ok2:
        return True, "Data Mi Account dihapus"
    return False, "Gagal — mungkin perlu root"


# ---------------------------------------------------------------------------
# Ekstraksi data khusus Xiaomi
# ---------------------------------------------------------------------------

_EKSTRAKSI: list[tuple[str, str, str]] = [
    ("Package terinstall",  "pm list packages -f",                "packages.txt"),
    ("Aplikasi pengguna",   "pm list packages -3",                "user_apps.txt"),
    ("Properti sistem",     "getprop",                            "properties.txt"),
    ("Proses berjalan",     "ps -A",                              "processes.txt"),
    ("Jaringan",            "ip addr",                            "network.txt"),
    ("Mount points",        "mount",                              "mounts.txt"),
    ("Akun tersimpan",      "dumpsys account",                    "accounts.txt"),
    ("MIUI settings global","settings list global",               "settings_global.txt"),
    ("MIUI settings secure","settings list secure",               "settings_secure.txt"),
    ("WiFi info",           "dumpsys wifi",                       "wifi.txt"),
    ("Baterai",             "dumpsys battery",                    "battery.txt"),
    ("Storage",             "df -h",                              "storage.txt"),
    ("Bluetooth",           "dumpsys bluetooth_manager",          "bluetooth.txt"),
    ("Telephony",           "dumpsys telephony.registry",         "telephony.txt"),
]


def ekstrak_data(serial: str, dir_out: Path) -> dict:
    dir_out.mkdir(parents=True, exist_ok=True)
    hasil: dict = {}
    for nama, cmd, fname in _EKSTRAKSI:
        ok, data = shell(serial, cmd, timeout=25)
        if ok and data:
            (dir_out / fname).write_text(data, encoding="utf-8")
            hasil[nama] = {"status": "OK", "file": fname, "bytes": len(data.encode())}
        else:
            hasil[nama] = {"status": "FAILED", "file": None, "bytes": 0}
    return hasil


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def tampilkan_header() -> None:
    console.print(
        Panel(
            Align.center(
                Text.from_markup(
                    "[bold cyan]Xiaomi[/bold cyan] [bold white]/[/bold white] "
                    "[bold yellow]POCO[/bold yellow] "
                    "[bold white]ADB Tool[/bold white]\n"
                    "[dim]Poco X3 NFC (surya/karna) — Version 1.0.0[/dim]"
                )
            ),
            style="bold blue",
            box=box.DOUBLE,
        )
    )


def cetak_baris(label: str, nilai: str, warna: str = CYAN) -> None:
    if nilai:
        console.print(f"[{DIM}]{label:<22}[/{DIM}]: [{warna}]{nilai}[/{warna}]")


def tampilkan_info(info: dict, rooted: bool, bl: str,
                   mi_account: tuple[bool, str], frp_google: str) -> None:
    console.print()
    console.print(
        Panel("[bold green][ADB] DEVICE INFO — XIAOMI / POCO[/bold green]",
              border_style="green")
    )
    console.print()

    log_ok = lambda lbl: console.print(f"{lbl} [bold green]OK[/bold green]")
    log_ok("Starting ADB Interface...")
    time.sleep(0.2)

    urutan = [
        ("Merek",             CYAN),
        ("Model",             CYAN),
        ("Codename",          KUNING),
        ("Nama Produk",       PUTIH),
        ("Pabrikan",          CYAN),
        ("Platform / SoC",    KUNING),
        ("CPU Arch",          PUTIH),
        ("Versi MIUI",        CYAN),
        ("Build MIUI",        PUTIH),
        ("Versi Android",     PUTIH),
        ("Android SDK",       PUTIH),
        ("Build ID",          PUTIH),
        ("Build Date",        PUTIH),
        ("Security Patch",    PUTIH),
        ("Serial",            CYAN),
        ("Timezone",          PUTIH),
        ("Bootloader",        PUTIH),
        ("Versi Bootloader",  PUTIH),
        ("Baseband",          PUTIH),
        ("Region",            PUTIH),
        ("Fingerprint",       DIM),
    ]

    for label, warna in urutan:
        cetak_baris(label, info.get(label, ""), warna)
        time.sleep(0.04)

    console.print()

    # Status penting
    bl_warna = HIJAU if bl == "UNLOCKED" else (MERAH if bl == "LOCKED" else KUNING)
    console.print(f"[{DIM}]Bootloader Status  [/{DIM}]: [{bl_warna}]{bl}[/{bl_warna}]")

    mi_aktif, mi_info = mi_account
    mi_warna = MERAH if mi_aktif else HIJAU
    mi_label = f"AKTIF — {mi_info}" if mi_aktif else f"TIDAK ADA — {mi_info}"
    console.print(f"[{DIM}]Mi Account         [/{DIM}]: [{mi_warna}]{mi_label}[/{mi_warna}]")

    frp_warna = HIJAU if "tidak ada" in frp_google.lower() else MERAH
    console.print(f"[{DIM}]Google FRP         [/{DIM}]: [{frp_warna}]{frp_google}[/{frp_warna}]")

    root_lbl  = "ROOTED" if rooted else "NOT ROOTED"
    root_warn = HIJAU if rooted else KUNING
    console.print(f"[{DIM}]Root Access        [/{DIM}]: [{root_warn}]{root_lbl}[/{root_warn}]")
    console.print(f"[{DIM}]Connection         [/{DIM}]: [{HIJAU}]ADB[/{HIJAU}]")


def tampilkan_tabel_frp(detail: list[tuple[str, bool]]) -> None:
    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column("m", style=DIM, width=30)
    tbl.add_column("s", justify="center")
    for nama, ok in detail:
        s = "[green]OK[/green]" if ok else "[dim]SKIP[/dim]"
        tbl.add_row(nama, s)
    console.print(tbl)


def tampilkan_tabel_ekstraksi(hasil: dict) -> None:
    tbl = Table(title="Hasil Ekstraksi Data", box=box.ROUNDED)
    tbl.add_column("Data",    style=CYAN)
    tbl.add_column("Status",  justify="center")
    tbl.add_column("Ukuran",  justify="right", style=DIM)
    tbl.add_column("File",    style=DIM)
    for nama, d in hasil.items():
        st    = "[green]OK[/green]" if d["status"] == "OK" else "[red]FAIL[/red]"
        ukuran = f"{d['bytes']:,} B" if d["bytes"] else "-"
        fname  = d["file"] or "-"
        tbl.add_row(nama, st, ukuran, fname)
    console.print(tbl)


# ---------------------------------------------------------------------------
# Pilih perangkat
# ---------------------------------------------------------------------------

def pilih_serial(serials: list[str], arg_serial: str) -> str | None:
    if arg_serial:
        if arg_serial in serials:
            return arg_serial
        console.print(f"[red]Serial '{arg_serial}' tidak ditemukan.[/red]")
        return None
    if len(serials) == 1:
        return serials[0]
    console.print("\n[bold]Pilih perangkat:[/bold]")
    for i, s in enumerate(serials, 1):
        console.print(f"  [{i}] {s}")
    while True:
        try:
            idx = int(input("Nomor perangkat: ")) - 1
            if 0 <= idx < len(serials):
                return serials[idx]
        except (ValueError, KeyboardInterrupt):
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Xiaomi / Poco X3 NFC ADB Tool"
    )
    p.add_argument("-s", "--serial",      default="",
                   help="Serial perangkat (otomatis jika tidak diisi)")
    p.add_argument("-o", "--output",      default="",
                   help="Direktori output ekstraksi")
    p.add_argument("--info-only",         action="store_true",
                   help="Hanya tampilkan info, tanpa hapus FRP")
    p.add_argument("--hapus-frp",         action="store_true",
                   help="Hapus Google FRP + Mi Account via ADB")
    p.add_argument("--ekstrak",           action="store_true",
                   help="Ekstraksi data forensik ke folder output")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    mulai = time.time()

    console.clear()
    tampilkan_header()

    # ─ Cek ADB
    if not cek_adb():
        console.print(Panel(
            "[red]ADB tidak ditemukan.[/red]\n"
            "Install: sudo apt install adb  |  brew install android-platform-tools",
            title="Error", border_style="red"
        ))
        return 1

    # ─ Scan perangkat
    console.print("\n[bold]Mencari perangkat Xiaomi / POCO...[/bold]")
    serials: list[str] = []
    for attempt in range(6):
        serials = daftar_perangkat()
        if serials:
            break
        if attempt < 5:
            console.print(f"  Menunggu... ({attempt + 1}/6)")
            time.sleep(3)

    if not serials:
        console.print(Panel(
            "[red]Tidak ada perangkat ditemukan.[/red]\n"
            "Pastikan:\n"
            "  1. Kabel USB terhubung\n"
            "  2. USB Debugging aktif (Pengaturan → Opsi Pengembang)\n"
            "  3. MIUI: aktifkan juga 'USB Debugging (Security)'\n"
            "  4. Coba: adb kill-server && adb start-server",
            title="Tidak Ada Perangkat", border_style="red"
        ))
        return 1

    console.print(f"[green]Ditemukan {len(serials)} perangkat[/green]")

    # ─ Pilih perangkat
    serial = pilih_serial(serials, args.serial)
    if not serial:
        return 1

    console.print(f"\n[dim]Perangkat: {serial}[/dim]")

    # ─ Baca info
    with console.status("Membaca info perangkat Xiaomi/MIUI..."):
        info       = baca_info(serial)
        rooted     = cek_root(serial)
        bl_status  = cek_bootloader(serial)
        mi_account = cek_mi_account(serial)
        frp_google = cek_frp_google(serial)

    # Deteksi Poco X3 NFC
    is_x3 = adalah_poco_x3_nfc(info)
    if is_x3:
        console.print(Panel(
            "[bold yellow]Poco X3 NFC terdeteksi![/bold yellow]\n"
            f"Codename: [cyan]{info.get('Codename', '?')}[/cyan]  "
            f"SoC: [cyan]{info.get('Platform / SoC', '?')}[/cyan]",
            border_style="yellow"
        ))

    tampilkan_info(info, rooted, bl_status, mi_account, frp_google)

    if args.info_only:
        console.print("\n[dim]--info-only: berhenti sebelum modifikasi.[/dim]")
        return 0

    # ─ Hapus FRP
    if args.hapus_frp:
        console.print(f"\n[bold blue]{'─' * 56}[/bold blue]")
        console.print(Panel("[bold]Menghapus FRP + Mi Account[/bold]", border_style="blue"))

        # Google FRP
        console.print("\n[bold]Google FRP:[/bold]")
        with console.status("Menghapus Google FRP..."):
            ok_frp, detail_frp = hapus_frp(serial)
        tampilkan_tabel_frp(detail_frp)
        if ok_frp:
            console.print("[green]Google FRP — selesai[/green]")
        else:
            console.print("[yellow]Google FRP — sebagian gagal[/yellow]")

        # Mi Account
        console.print("\n[bold]Mi Account:[/bold]")
        with console.status("Menghapus data Mi Account..."):
            ok_mi, msg_mi = hapus_mi_account(serial)
        if ok_mi:
            console.print(f"[green]Mi Account — {msg_mi}[/green]")
        else:
            console.print(f"[yellow]Mi Account — {msg_mi}[/yellow]")

    # ─ Ekstraksi
    if args.ekstrak:
        console.print(f"\n[bold blue]{'─' * 56}[/bold blue]")
        console.print(Panel("[bold]Ekstraksi Data Forensik[/bold]", border_style="blue"))

        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_out = Path(args.output or f"xiaomi_forensic_{ts}") / serial
        console.print(f"Output: [cyan]{dir_out.resolve()}[/cyan]\n")

        with console.status("Mengekstrak..."):
            hasil = ekstrak_data(serial, dir_out)

        tampilkan_tabel_ekstraksi(hasil)

        # Simpan laporan JSON
        laporan = {
            "timestamp": ts,
            "serial":    serial,
            "info":      info,
            "rooted":    rooted,
            "bootloader": bl_status,
            "mi_account": {"aktif": mi_account[0], "info": mi_account[1]},
            "frp_google": frp_google,
            "ekstraksi":  hasil,
        }
        path_laporan = dir_out / "laporan.json"
        path_laporan.write_text(
            json.dumps(laporan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        console.print(f"\nLaporan JSON: [cyan]{path_laporan.resolve()}[/cyan]")

    # ─ Footer
    elapsed = round(time.time() - mulai)
    console.print(f"\n[dim]Xiaomi / POCO ADB Tool — Elapsed time : {elapsed} seconds[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
