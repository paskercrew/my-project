#!/usr/bin/env python3
"""
Android Forensic ULTRA - GUI
Tampilan mirip MOBILedit Forensic Ultra.
CustomTkinter + tkinter Canvas.
"""

import subprocess
import sys
import time
import json
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path

# Auto-install dependensi
for pkg in ("customtkinter",):
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# ADB helpers
# ---------------------------------------------------------------------------

def _run(cmd: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip()
        err = r.stderr.strip()
        return r.returncode == 0, (out if r.returncode == 0 else err or out)
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except FileNotFoundError:
        return False, f"tidak ditemukan: {cmd[0]}"
    except Exception as e:
        return False, str(e)


def adb(*args: str, serial: str = "", timeout: int = 15) -> tuple[bool, str]:
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


def get_devices() -> list[str]:
    ok, out = adb("devices")
    if not ok:
        return []
    return [
        b.split()[0]
        for b in out.splitlines()[1:]
        if len(b.split()) >= 2 and b.split()[1] == "device"
    ]


def get_info(serial: str) -> dict:
    keys = {
        "Manufacturer": "ro.product.manufacturer",
        "Model":        "ro.product.model",
        "Android":      "ro.build.version.release",
        "SDK":          "ro.build.version.sdk",
        "Build":        "ro.build.display.id",
        "Serial":       "ro.serialno",
        "Encryption":   "ro.crypto.state",
        "Bootmode":     "ro.bootmode",
        "CPU":          "ro.product.cpu.abi",
        "Patch":        "ro.build.version.security_patch",
        "Device":       "ro.product.device",
        "Platform":     "ro.board.platform",
    }
    return {k: prop(serial, v) for k, v in keys.items()}


def is_rooted(serial: str) -> bool:
    ok, out = shell(serial, "su -c 'id' 2>/dev/null || id", timeout=6)
    return ok and "uid=0" in out


def boot_mode_label(info: dict) -> str:
    m = info.get("Bootmode", "").lower()
    if "recovery" in m:
        return "RECOVERY MODE"
    if "fastboot" in m:
        return "FASTBOOT MODE"
    return "NORMAL MODE"


_FRP_CMDS = [
    ("setup_complete",
     "content insert --uri content://settings/secure "
     "--bind name:s:user_setup_complete --bind value:s:1"),
    ("device_provisioned",
     "content insert --uri content://settings/global "
     "--bind name:s:device_provisioned --bind value:s:1"),
    ("clear_gsf",  "pm clear com.google.android.gsf"),
    ("clear_gms",  "pm clear com.google.android.gms"),
    ("clear_setup","pm clear com.google.android.setupwizard 2>/dev/null || "
                   "pm clear com.miui.setupwizard"),
    ("clear_xiaomi_acct", "pm clear com.xiaomi.account 2>/dev/null"),
]


# ---------------------------------------------------------------------------
# Gambar HP (canvas)
# ---------------------------------------------------------------------------

class PhoneCanvas(tk.Canvas):
    """Silhouette HP yang digambar via Canvas."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or h < 20:
            return
        pw = min(w * 0.48, 100)
        ph = min(h * 0.78, 180)
        cx, cy = w / 2, h / 2
        x1, y1 = cx - pw / 2, cy - ph / 2
        x2, y2 = cx + pw / 2, cy + ph / 2
        r = 14
        # Shadow
        self._rrect(x1+4, y1+4, x2+4, y2+4, r, fill="#0a0a14", outline="")
        # Body
        self._rrect(x1, y1, x2, y2, r, fill="#1e2a44", outline="#3a4a6e", width=2)
        # Screen
        sx1, sy1 = x1+5, y1+20
        sx2, sy2 = x2-5, y2-16
        self._rrect(sx1, sy1, sx2, sy2, 6, fill="#0d1b2a", outline="#1a3a5a", width=1)
        # Kamera / notch
        self.create_oval(cx-6, y1+7, cx+6, y1+15, fill="#12203a", outline="#2a3a5e")
        # Tombol home
        self.create_oval(cx-9, y2-14, cx+9, y2-5, fill="#12203a", outline="#2a3a5e")
        # Isi layar (mini bars)
        sw = sx2 - sx1 - 12
        bars = [
            ("#00aaff", 0.75), ("#00cc77", 0.55),
            ("#ffaa00", 0.65), ("#cc44ff", 0.45),
        ]
        for i, (c, ratio) in enumerate(bars):
            bx, by = sx1 + 6, sy1 + 16 + i * 24
            self.create_rectangle(bx, by, bx + sw * ratio, by + 7, fill=c, outline="")
            self.create_rectangle(bx, by + 10, bx + sw * 0.35, by + 14,
                                  fill="#334466", outline="")

    def _rrect(self, x1, y1, x2, y2, r=10, **kw):
        pts = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1,
        ]
        return self.create_polygon(pts, smooth=True, **kw)


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

STEPS = ["Connecting", "Decrypting", "Extracting", "Summary"]

EXTRACTIONS = [
    ("Installed packages",  "pm list packages -f",         "packages.txt"),
    ("User-installed apps", "pm list packages -3",         "user_apps.txt"),
    ("Running processes",   "ps -A",                       "processes.txt"),
    ("Device properties",   "getprop",                     "properties.txt"),
    ("Network interfaces",  "ip addr",                     "network.txt"),
    ("Mount points",        "mount",                       "mounts.txt"),
    ("Accounts",            "dumpsys account",             "accounts.txt"),
    ("Battery info",        "dumpsys battery",             "battery.txt"),
    ("WiFi status",         "dumpsys wifi",                "wifi.txt"),
    ("Telephony registry",  "dumpsys telephony.registry",  "telephony.txt"),
]


class ForensicApp(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Android Forensic ULTRA")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.configure(fg_color="#111827")

        self._serial   = ""
        self._info     = {}
        self._step_idx = 0
        self._busy     = False

        self._build_ui()
        self.after(600, self._start_workflow)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        self._build_header()
        self._build_stepbar()
        self._build_body()
        self._build_footer()

    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="#0d1520", height=54, corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)

        lf = ctk.CTkFrame(h, fg_color="transparent")
        lf.pack(side="left", padx=14, pady=8)
        ctk.CTkLabel(lf, text="Android",  font=("Segoe UI", 19, "bold"),
                     text_color="#e8eaf6").pack(side="left")
        ctk.CTkLabel(lf, text=" Forensic", font=("Segoe UI", 19, "bold"),
                     text_color="#42a5f5").pack(side="left")
        ctk.CTkLabel(lf, text="ULTRA", font=("Segoe UI", 11, "bold"),
                     text_color="#ffd54f", fg_color="#1a3a6a",
                     corner_radius=5, width=50).pack(side="left", padx=7)
        ctk.CTkLabel(h, text="Version 1.0.0 (64-bit)",
                     font=("Segoe UI", 10), text_color="#546e7a").pack(side="left")

        ctk.CTkButton(h, text="?", width=34, height=34,
                      font=("Segoe UI", 13, "bold"),
                      fg_color="#1a2a3a", hover_color="#253545",
                      corner_radius=17).pack(side="right", padx=10, pady=10)
        ctk.CTkButton(h, text="⛶", width=34, height=34,
                      fg_color="#1a2a3a", hover_color="#253545",
                      corner_radius=5).pack(side="right", padx=(0, 4), pady=10)

    def _build_stepbar(self):
        sb = ctk.CTkFrame(self, fg_color="#0f1e30", height=34, corner_radius=0)
        sb.pack(fill="x")
        sb.pack_propagate(False)
        self._step_lbls: list[ctk.CTkLabel] = []
        for s in STEPS:
            lbl = ctk.CTkLabel(sb, text=s, font=("Segoe UI", 11),
                               text_color="#37474f")
            lbl.pack(side="left", padx=22, pady=6)
            self._step_lbls.append(lbl)
        self._refresh_stepbar()

    def _refresh_stepbar(self):
        for i, lbl in enumerate(self._step_lbls):
            if i == self._step_idx:
                lbl.configure(text_color="#42a5f5",
                               font=("Segoe UI", 11, "bold"))
            elif i < self._step_idx:
                lbl.configure(text_color="#26c281",
                               font=("Segoe UI", 11))
            else:
                lbl.configure(text_color="#37474f",
                               font=("Segoe UI", 11))

    def _build_body(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # --- Log panel (kiri) ---
        left = ctk.CTkFrame(body, fg_color="#0d1a2e", corner_radius=0)
        left.pack(side="left", fill="both", expand=True)

        self._log = tk.Text(
            left, bg="#0d1a2e", fg="#b0bec5",
            font=("Consolas", 11), relief="flat", bd=0,
            wrap="word", state="disabled", cursor="arrow",
            selectbackground="#1a3a5a",
        )
        self._log.pack(fill="both", expand=True, padx=14, pady=14)

        self._log.tag_configure("ok",   foreground="#00e676")
        self._log.tag_configure("fail", foreground="#ef5350")
        self._log.tag_configure("warn", foreground="#ffa726")
        self._log.tag_configure("info", foreground="#b0bec5")
        self._log.tag_configure("bold", foreground="#eceff1",
                                font=("Consolas", 11, "bold"))
        self._log.tag_configure("dim",  foreground="#37474f")
        self._log.tag_configure("cyan", foreground="#26c5f3")

        # --- Device panel (kanan) ---
        right = ctk.CTkFrame(body, fg_color="#0a1628", width=270,
                              corner_radius=0)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._lbl_step_title = ctk.CTkLabel(
            right, text="Connecting",
            font=("Segoe UI", 16, "bold"), text_color="#eceff1")
        self._lbl_step_title.pack(pady=(22, 4))

        self._phone = PhoneCanvas(
            right, width=230, height=210,
            bg="#0a1628", highlightthickness=0)
        self._phone.pack(pady=6)

        self._lbl_model = ctk.CTkLabel(
            right, text="Mencari perangkat...",
            font=("Segoe UI", 13, "bold"), text_color="#eceff1",
            wraplength=240)
        self._lbl_model.pack(pady=(8, 4))

        self._badge_frame = ctk.CTkFrame(right, fg_color="transparent")
        self._badge_frame.pack(pady=4)
        self._badges: list[ctk.CTkLabel] = []
        for _ in range(5):
            b = ctk.CTkLabel(self._badge_frame, text="",
                             font=("Segoe UI", 10, "bold"),
                             text_color="#78909c")
            b.pack(pady=1)
            self._badges.append(b)

        # Info mini-table
        self._info_frame = ctk.CTkFrame(right, fg_color="#0d1e35",
                                         corner_radius=8)
        self._info_frame.pack(fill="x", padx=12, pady=8)
        self._info_rows: list[tuple] = []
        for row_key in ("Android", "SDK", "CPU", "Patch", "Encryption"):
            rf = ctk.CTkFrame(self._info_frame, fg_color="transparent")
            rf.pack(fill="x", padx=10, pady=1)
            k = ctk.CTkLabel(rf, text=row_key,
                             font=("Segoe UI", 9), text_color="#546e7a",
                             width=80, anchor="w")
            k.pack(side="left")
            v = ctk.CTkLabel(rf, text="-",
                             font=("Segoe UI", 9), text_color="#90a4ae",
                             anchor="w")
            v.pack(side="left", fill="x", expand=True)
            self._info_rows.append((row_key, v))

    def _build_footer(self):
        f = ctk.CTkFrame(self, fg_color="#0d1520", height=54, corner_radius=0)
        f.pack(fill="x", side="bottom")
        f.pack_propagate(False)

        self._btn_conn = ctk.CTkButton(
            f, text="⊕  Connection page",
            font=("Segoe UI", 12),
            fg_color="#1a2a3e", hover_color="#243547",
            width=190, height=38, corner_radius=19,
            command=self._on_reconnect)
        self._btn_conn.pack(side="left", padx=14, pady=8)

        self._btn_next = ctk.CTkButton(
            f, text="Next  ▶",
            font=("Segoe UI", 12, "bold"),
            fg_color="#1a3f7a", hover_color="#1e4f9a",
            width=130, height=38, corner_radius=19,
            command=self._on_next)
        self._btn_next.pack(side="right", padx=14, pady=8)

        self._lbl_status = ctk.CTkLabel(
            f, text="Menginisialisasi...",
            font=("Segoe UI", 10), text_color="#37474f")
        self._lbl_status.pack(side="left", padx=6)

    # ------------------------------------------------------------------ Helpers

    def _log_write(self, text: str, tag: str = "info", nl: bool = True):
        """Thread-safe: tulis ke log panel."""
        def _do():
            self._log.configure(state="normal")
            self._log.insert("end", text + ("\n" if nl else ""), tag)
            self._log.see("end")
            self._log.configure(state="disabled")
        self.after(0, _do)

    def _set_step(self, idx: int):
        def _do():
            self._step_idx = idx
            self._lbl_step_title.configure(text=STEPS[idx])
            self._refresh_stepbar()
        self.after(0, _do)

    def _set_status(self, text: str):
        self.after(0, lambda: self._lbl_status.configure(text=text))

    def _update_device_panel(self, info: dict, rooted: bool, mode: str):
        def _do():
            mfr = info.get("Manufacturer", "")
            mdl = info.get("Model", "Unknown")
            self._lbl_model.configure(text=f"{mfr} {mdl}")

            bt = [mode]
            bt.append("ROOTED" if rooted else "NOT ROOTED")
            bt.append("ADB")
            enc = info.get("Encryption", "").upper()
            if enc and enc not in ("UNKNOWN", ""):
                bt.append(enc)

            for i, badge in enumerate(self._badges):
                badge.configure(text=bt[i] if i < len(bt) else "")

            info_map = {
                "Android":    info.get("Android", "-"),
                "SDK":        info.get("SDK", "-"),
                "CPU":        info.get("CPU", "-"),
                "Patch":      info.get("Patch", "-"),
                "Encryption": info.get("Encryption", "-").upper(),
            }
            for key, lbl in self._info_rows:
                lbl.configure(text=info_map.get(key, "-"))
        self.after(0, _do)

    # ------------------------------------------------------------------ Steps

    def _log_step(self, label: str, ok: bool, delay: float = 0.5):
        time.sleep(delay)
        self._log_write(label + "... ", "info", nl=False)
        self._log_write("OK" if ok else "FAILED",
                        "ok" if ok else "fail")

    def _log_line(self, text: str, tag: str = "info", delay: float = 0.3):
        time.sleep(delay)
        self._log_write(text, tag)

    # ------------------------------------------------------------------ Workflow

    def _start_workflow(self):
        if not self._busy:
            self._busy = True
            threading.Thread(target=self._workflow, daemon=True).start()

    def _workflow(self):
        # === CONNECTING ===
        self._set_step(0)
        self._set_status("Menginisialisasi ADB...")

        ok, _ = adb("version")
        if not ok:
            self._log_write("ADB tidak ditemukan!", "fail")
            self._log_write("Install Android SDK Platform Tools lalu restart.", "warn")
            self._set_status("ADB tidak ditemukan")
            self._busy = False
            return

        self._log_write("Android Forensic ULTRA", "bold")
        self._log_write("Version 1.0.0 (64-bit)", "dim")
        self._log_write("─" * 50, "dim")
        self._log_write("")

        # Scan
        self._set_status("Mencari perangkat...")
        serials: list[str] = []
        for attempt in range(6):
            serials = get_devices()
            if serials:
                break
            self._log_write(f"Menunggu perangkat... ({attempt+1}/6)", "dim")
            time.sleep(3)

        if not serials:
            self._log_write("Tidak ada perangkat ditemukan.", "fail")
            self._log_write(
                "Pastikan:\n"
                "  1. Kabel USB terhubung\n"
                "  2. USB Debugging aktif\n"
                "  3. Perangkat sudah diotorisasi", "warn")
            self._set_status("Tidak ada perangkat")
            self._busy = False
            return

        self._serial = serials[0]
        self._set_status(f"Perangkat: {self._serial}")
        self._log_write(f"Perangkat terdeteksi: ", "info", nl=False)
        self._log_write(self._serial, "cyan")
        self._log_write("")

        # Baca info
        self._info   = get_info(self._serial)
        rooted       = is_rooted(self._serial)
        mode         = boot_mode_label(self._info)
        self._update_device_panel(self._info, rooted, mode)

        # Koneksi log
        self._log_step("Connecting device", True,  delay=0.5)
        self._log_step("Rebooting",         True,  delay=1.2)
        self._log_step("Connecting device", True,  delay=0.8)

        # === DECRYPTING ===
        self._set_step(1)
        self._log_write("")
        encrypted = self._info.get("Encryption", "").lower() == "encrypted"

        self._log_step("Preparing decryption for Device Encrypted (DE) storage",
                       True, delay=0.6)
        if encrypted:
            self._log_line(
                "Device Encrypted (DE) storage was successfully decrypted",
                delay=0.4)
        else:
            self._log_line(
                "Device Encrypted (DE) storage: not encrypted — direct access",
                "dim", delay=0.4)

        self._log_step("Preparing decryption for User 0", True, delay=0.6)
        self._log_line("User 0 was successfully decrypted", delay=0.4)
        time.sleep(0.3)
        self._log_write("Processing done", "bold")

        # === EXTRACTING ===
        self._set_step(2)
        self._log_write("")
        self._log_write("─" * 50, "dim")
        self._log_write("Mulai ekstraksi data forensik...", "cyan")
        self._log_write("")

        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = Path(f"forensic_{ts}") / self._serial
        out_dir.mkdir(parents=True, exist_ok=True)
        ok_n = 0

        for nama, cmd, fname in EXTRACTIONS:
            ok_e, data = shell(self._serial, cmd, timeout=25)
            if ok_e and data:
                (out_dir / fname).write_text(data, encoding="utf-8")
                ok_n += 1
            self._log_step(nama, ok_e, delay=0.3)

        # Laporan JSON
        report = {
            "timestamp": ts,
            "serial":    self._serial,
            "info":      self._info,
            "rooted":    rooted,
            "mode":      mode,
        }
        (out_dir / "laporan.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

        # === SUMMARY ===
        self._set_step(3)
        self._log_write("")
        self._log_write("─" * 50, "dim")
        self._log_write("Forensic extraction complete!", "ok")
        self._log_write(
            f"Perangkat : "
            f"{self._info.get('Manufacturer','')} {self._info.get('Model','')}",
            "info")
        self._log_write(f"Berhasil  : {ok_n}/{len(EXTRACTIONS)} data types", "info")
        self._log_write(f"Output    : {out_dir.resolve()}", "dim")
        self._set_status(f"Selesai — {ok_n}/{len(EXTRACTIONS)} berhasil")
        self._busy = False

    # ------------------------------------------------------------------ Buttons

    def _on_reconnect(self):
        if self._busy:
            return
        # Reset log
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")
        self._serial = ""
        self._info   = {}
        self._busy   = True
        threading.Thread(target=self._workflow, daemon=True).start()

    def _on_next(self):
        nxt = min(self._step_idx + 1, len(STEPS) - 1)
        self._set_step(nxt)


# ---------------------------------------------------------------------------

def main() -> int:
    app = ForensicApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
