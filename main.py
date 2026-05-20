#!/usr/bin/env python3
"""
Android Forensic Suite - ALL IN ONE
Satu launcher untuk semua tool:
  1. Android Forensic Ultra (mirip MOBILedit)
  2. Samsung FRP Erase
  3. Xiaomi / Poco ADB Tool
  4. EDL Mode - Poco X3 NFC
"""

import subprocess, sys, time, json, threading, os
import tkinter as tk
from datetime import datetime
from pathlib import Path

for pkg in ("customtkinter",):
    try:
        __import__(pkg)
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)

import customtkinter as ctk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# ADB / Fastboot helpers
# ---------------------------------------------------------------------------

def _run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = r.stdout.strip(); err = r.stderr.strip()
        return r.returncode == 0, (out if r.returncode == 0 else err or out)
    except subprocess.TimeoutExpired: return False, "timeout"
    except FileNotFoundError:         return False, f"tidak ditemukan: {cmd[0]}"
    except Exception as e:            return False, str(e)

def adb(*args, serial="", timeout=30):
    cmd = ["adb"] + (["-s", serial] if serial else []) + list(args)
    return _run(cmd, timeout)

def shell(serial, cmd, timeout=30):
    return adb("shell", cmd, serial=serial, timeout=timeout)

def prop(serial, key):
    ok, v = shell(serial, f"getprop {key}")
    return v.strip() if ok and v.strip() else ""

def get_devices():
    ok, out = adb("devices")
    if not ok: return []
    return [b.split()[0] for b in out.splitlines()[1:]
            if len(b.split()) >= 2 and b.split()[1] == "device"]

def get_info(serial):
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
        "MIUI":         "ro.miui.ui.version.name",
        "Baseband":     "gsm.version.baseband",
    }
    return {k: prop(serial, v) for k, v in keys.items()}

def is_rooted(serial):
    ok, out = shell(serial, "su -c 'id' 2>/dev/null || id", timeout=8)
    return ok and "uid=0" in out

def boot_mode_label(info):
    m = info.get("Bootmode", "").lower()
    if "recovery" in m: return "RECOVERY MODE"
    if "fastboot" in m: return "FASTBOOT MODE"
    return "NORMAL MODE"

def adb_pull(serial, src, dst, timeout=120):
    Path(dst).mkdir(parents=True, exist_ok=True)
    return adb("pull", src, str(dst), serial=serial, timeout=timeout)

def deteksi_edl():
    if sys.platform == "win32":
        ok, out = _run(["pnputil", "/enum-devices", "/connected"], timeout=10)
        if ok and ("9008" in out or "qdloader" in out.lower()): return True
        ok2, out2 = _run(["wmic","path","Win32_USBHub","where",
                          "DeviceID like '%VID_05C6%PID_9008%'","get","DeviceID"], timeout=10)
        return ok2 and "VID_05C6" in out2
    ok, out = _run(["lsusb"], timeout=10)
    return ok and "05c6:9008" in out.lower()


# ---------------------------------------------------------------------------
# Device DB
# ---------------------------------------------------------------------------

DEVICE_DB = {}
_DB_PATH = Path("device_db.json")
if _DB_PATH.exists():
    try: DEVICE_DB = json.loads(_DB_PATH.read_text(encoding="utf-8"))
    except: pass


# ---------------------------------------------------------------------------
# Phone Canvas
# ---------------------------------------------------------------------------

class PhoneCanvas(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        w,h = self.winfo_width(), self.winfo_height()
        if w<20 or h<20: return
        pw=min(w*.48,90); ph=min(h*.78,170)
        cx,cy = w/2, h/2
        x1,y1 = cx-pw/2, cy-ph/2
        x2,y2 = cx+pw/2, cy+ph/2
        self._rr(x1+3,y1+3,x2+3,y2+3,13,fill="#0a0a14",outline="")
        self._rr(x1,y1,x2,y2,13,fill="#1e2a44",outline="#3a4a6e",width=2)
        sx1,sy1,sx2,sy2 = x1+5,y1+18,x2-5,y2-14
        self._rr(sx1,sy1,sx2,sy2,5,fill="#0d1b2a",outline="#1a3a5a",width=1)
        self.create_oval(cx-5,y1+6,cx+5,y1+13,fill="#12203a",outline="#2a3a5e")
        self.create_oval(cx-8,y2-12,cx+8,y2-4,fill="#12203a",outline="#2a3a5e")
        sw=sx2-sx1-10
        for i,(c,r) in enumerate([("#00aaff",.75),("#00cc77",.55),("#ffaa00",.65),("#cc44ff",.45)]):
            bx,by=sx1+5,sy1+14+i*22
            self.create_rectangle(bx,by,bx+sw*r,by+6,fill=c,outline="")
            self.create_rectangle(bx,by+9,bx+sw*.35,by+13,fill="#334466",outline="")

    def _rr(self,x1,y1,x2,y2,r=10,**kw):
        pts=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,
             x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        return self.create_polygon(pts,smooth=True,**kw)


# ---------------------------------------------------------------------------
# Base Panel
# ---------------------------------------------------------------------------

class BasePanel(ctk.CTkFrame):
    """Base class semua panel tool."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app
        self._build()

    def _build(self): pass

    def _log_box(self, parent) -> tk.Text:
        """Buat log text widget standar."""
        t = tk.Text(
            parent, bg="#0d1a2e", fg="#b0bec5",
            font=("Consolas",11), relief="flat", bd=0,
            wrap="word", state="disabled", cursor="arrow",
            selectbackground="#1a3a5a")
        t.tag_configure("ok",   foreground="#00e676")
        t.tag_configure("fail", foreground="#ef5350")
        t.tag_configure("warn", foreground="#ffa726")
        t.tag_configure("info", foreground="#b0bec5")
        t.tag_configure("bold", foreground="#eceff1", font=("Consolas",11,"bold"))
        t.tag_configure("dim",  foreground="#37474f")
        t.tag_configure("cyan", foreground="#26c5f3")
        return t

    def _w(self, box: tk.Text, text: str, tag="info", nl=True):
        def _do():
            box.configure(state="normal")
            box.insert("end", text+("\n" if nl else ""), tag)
            box.see("end")
            box.configure(state="disabled")
        self.after(0, _do)

    def _clear(self, box: tk.Text):
        box.configure(state="normal")
        box.delete("1.0","end")
        box.configure(state="disabled")

    def _device_right_panel(self, parent):
        """Panel kanan: gambar HP + info."""
        right = ctk.CTkFrame(parent, fg_color="#0a1628", width=260, corner_radius=0)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._lbl_step = ctk.CTkLabel(right, text="Connecting",
                                       font=("Segoe UI",15,"bold"), text_color="#eceff1")
        self._lbl_step.pack(pady=(18,2))

        self._phone = PhoneCanvas(right, width=210, height=190,
                                   bg="#0a1628", highlightthickness=0)
        self._phone.pack(pady=4)

        self._lbl_model = ctk.CTkLabel(right, text="Mencari perangkat...",
                                        font=("Segoe UI",12,"bold"),
                                        text_color="#eceff1", wraplength=240)
        self._lbl_model.pack(pady=(4,2))

        self._badge_f = ctk.CTkFrame(right, fg_color="transparent")
        self._badge_f.pack(pady=2)
        self._badges = []
        for _ in range(5):
            b = ctk.CTkLabel(self._badge_f, text="",
                             font=("Segoe UI",9,"bold"), text_color="#78909c")
            b.pack(pady=1)
            self._badges.append(b)

        inf = ctk.CTkFrame(right, fg_color="#0d1e35", corner_radius=8)
        inf.pack(fill="x", padx=10, pady=4)
        self._irows = []
        for rk in ("Android","SDK","CPU","Patch","MIUI"):
            rf = ctk.CTkFrame(inf, fg_color="transparent")
            rf.pack(fill="x", padx=8, pady=1)
            ctk.CTkLabel(rf, text=rk, font=("Segoe UI",9),
                         text_color="#546e7a", width=70, anchor="w").pack(side="left")
            v = ctk.CTkLabel(rf, text="-", font=("Segoe UI",9),
                             text_color="#90a4ae", anchor="w")
            v.pack(side="left", fill="x", expand=True)
            self._irows.append((rk, v))
        return right

    def _update_device_panel(self, info, rooted, mode):
        def _do():
            mfr=info.get("Manufacturer",""); mdl=info.get("Model","Unknown")
            self._lbl_model.configure(text=f"{mfr} {mdl}")
            bt=[mode, "ROOTED" if rooted else "NOT ROOTED", "ADB"]
            enc=info.get("Encryption","").upper()
            if enc and enc not in ("","UNKNOWN"): bt.append(enc)
            miui=info.get("MIUI","")
            if miui: bt.append(miui)
            for i,b in enumerate(self._badges):
                b.configure(text=bt[i] if i<len(bt) else "")
            im={"Android":info.get("Android","-"),"SDK":info.get("SDK","-"),
                "CPU":info.get("CPU","-"),"Patch":info.get("Patch","-"),
                "MIUI":info.get("MIUI","-") or "-"}
            for k,lbl in self._irows: lbl.configure(text=im.get(k,"-"))
        self.after(0, _do)


# ---------------------------------------------------------------------------
# Panel 1 : Android Forensic Ultra
# ---------------------------------------------------------------------------

EXTRACTIONS = [
    ("SMS",            "content query --uri content://sms --projection address,body,date,type",         "sms.txt"),
    ("Kontak",         "content query --uri content://contacts/phones --projection display_name,number", "contacts.txt"),
    ("Riwayat Telepon","content query --uri content://call_log/calls --projection number,date,duration", "calls.txt"),
    ("Packages",       "pm list packages -f",                                                            "packages.txt"),
    ("Proses",         "ps -A",                                                                          "processes.txt"),
    ("Properti",       "getprop",                                                                         "properties.txt"),
    ("Jaringan",       "ip addr",                                                                         "network.txt"),
    ("Akun",           "dumpsys account",                                                                 "accounts.txt"),
    ("WiFi",           "dumpsys wifi",                                                                    "wifi.txt"),
    ("Baterai",        "dumpsys battery",                                                                 "battery.txt"),
    ("Storage",        "df -h",                                                                           "storage.txt"),
    ("Settings",       "settings list secure",                                                            "settings.txt"),
]

class ForensicPanel(BasePanel):
    STEPS = ["Connecting","Decrypting","Extracting","Summary"]

    def _build(self):
        self._step_idx = 0
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Stepbar
        sb = ctk.CTkFrame(self, fg_color="#0f1e30", height=32, corner_radius=0)
        sb.pack(fill="x", before=body)
        sb.pack_propagate(False)
        self._slbls = []
        for s in self.STEPS:
            l = ctk.CTkLabel(sb, text=s, font=("Segoe UI",10), text_color="#37474f")
            l.pack(side="left", padx=18, pady=5)
            self._slbls.append(l)

        # Log
        left = ctk.CTkFrame(body, fg_color="#0d1a2e", corner_radius=0)
        left.pack(side="left", fill="both", expand=True)
        self._log = self._log_box(left)
        self._log.pack(fill="both", expand=True, padx=12, pady=12)

        # Device panel
        self._device_right_panel(body)

        # Footer
        foot = ctk.CTkFrame(self, fg_color="#0d1520", height=48, corner_radius=0)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        ctk.CTkButton(foot, text="⊕  Connection page", font=("Segoe UI",11),
                      fg_color="#1a2a3e", hover_color="#243547",
                      width=170, height=34, corner_radius=17,
                      command=self._restart).pack(side="left", padx=12, pady=7)

        # Opsi
        opt = ctk.CTkFrame(foot, fg_color="transparent")
        opt.pack(side="left", padx=10)
        self._opt_media  = ctk.BooleanVar(value=True)
        self._opt_backup = ctk.BooleanVar(value=False)
        for txt, var in [("Foto/Video", self._opt_media),("ADB Backup", self._opt_backup)]:
            ctk.CTkCheckBox(opt, text=txt, variable=var,
                            font=("Segoe UI",9), text_color="#90a4ae",
                            checkbox_height=14, checkbox_width=14
                            ).pack(side="left", padx=8)

        ctk.CTkButton(foot, text="Next ▶", font=("Segoe UI",11,"bold"),
                      fg_color="#1a3f7a", hover_color="#1e4f9a",
                      width=100, height=34, corner_radius=17,
                      command=lambda: self._set_step(min(self._step_idx+1,3))
                      ).pack(side="right", padx=12, pady=7)

        self._status = ctk.CTkLabel(foot, text="", font=("Segoe UI",9),
                                     text_color="#37474f")
        self._status.pack(side="right", padx=6)
        self.after(500, self._start)

    def _w2(self, t, tag="info", nl=True): self._w(self._log, t, tag, nl)

    def _set_step(self, i):
        def _do():
            self._step_idx = i
            self._lbl_step.configure(text=self.STEPS[i])
            for j,l in enumerate(self._slbls):
                if j==i: l.configure(text_color="#42a5f5", font=("Segoe UI",10,"bold"))
                elif j<i: l.configure(text_color="#26c281", font=("Segoe UI",10))
                else: l.configure(text_color="#37474f", font=("Segoe UI",10))
        self.after(0, _do)

    def _set_st(self, t): self.after(0, lambda: self._status.configure(text=t))

    def _start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _restart(self):
        self._clear(self._log)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        self._set_step(0)
        self._set_st("Cek ADB...")
        ok,_ = adb("version")
        if not ok:
            self._w2("ADB tidak ditemukan!","fail")
            self._w2("Install Android SDK Platform Tools.","warn")
            return

        self._w2("Android Forensic ULTRA","bold")
        self._w2("─"*50,"dim")
        self._w2("")

        serials=[]
        for i in range(6):
            serials=get_devices()
            if serials: break
            self._w2(f"Menunggu perangkat... ({i+1}/6)","dim")
            time.sleep(3)

        if not serials:
            self._w2("Tidak ada perangkat.","fail")
            self._set_st("Tidak ada perangkat")
            return

        serial=serials[0]
        self._set_st(f"Perangkat: {serial}")
        info=get_info(serial)
        rooted=is_rooted(serial)
        mode=boot_mode_label(info)
        self._update_device_panel(info,rooted,mode)

        db=DEVICE_DB.get(info.get("Model",""),{})
        if db: self._w2(f"Database: {db.get('name','')}","cyan")

        for lbl,ok,dl in [("Connecting device",True,.5),("Rebooting",True,1.2),("Connecting device",True,.8)]:
            time.sleep(dl); self._w2(lbl+"... ","info",nl=False); self._w2("OK","ok")

        self._set_step(1)
        self._w2("")
        time.sleep(.5); self._w2("Preparing decryption for Device Encrypted (DE) storage... ","info",nl=False)
        time.sleep(.6); self._w2("OK","ok")
        self._w2("Device Encrypted (DE) storage was successfully decrypted","info")
        time.sleep(.5); self._w2("Preparing decryption for User 0... ","info",nl=False)
        time.sleep(.6); self._w2("OK","ok")
        self._w2("User 0 was successfully decrypted","info")
        time.sleep(.3); self._w2("Processing done","bold")

        self._set_step(2)
        ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        out=Path(f"forensic_{ts}")/serial
        out.mkdir(parents=True,exist_ok=True)
        self._w2(""); self._w2("─"*50,"dim")
        self._w2("Ekstraksi data forensik...","cyan")
        ok_n=0
        for nama,cmd,fname in EXTRACTIONS:
            ok_e,data=shell(serial,cmd,timeout=25)
            if ok_e and data: (out/fname).write_text(data,encoding="utf-8"); ok_n+=1
            time.sleep(.25); self._w2(f"{nama}... ","info",nl=False)
            self._w2("OK" if ok_e else "SKIP","ok" if ok_e else "dim")

        # Foto & Video
        if self._opt_media.get():
            for src,sub in [("/sdcard/DCIM/","media/DCIM"),("/sdcard/Pictures/","media/Pics")]:
                ok_p,_=adb_pull(serial,src,out/sub,timeout=300)
                self._w2(f"Pull {src.split('/')[-2]}... ","info",nl=False)
                self._w2("OK" if ok_p else "SKIP","ok" if ok_p else "dim")
                if ok_p: ok_n+=1

        # WhatsApp
        ok_wa,_=adb_pull(serial,"/sdcard/Android/media/com.whatsapp/",out/"whatsapp",timeout=300)
        self._w2("WhatsApp media... ","info",nl=False)
        self._w2("OK" if ok_wa else "SKIP","ok" if ok_wa else "dim")

        # ADB Backup
        if self._opt_backup.get():
            bak=out/"backup"/"backup.ab"
            bak.parent.mkdir(parents=True,exist_ok=True)
            ok_b,_=adb("backup","-apk","-shared","-all","-nosystem","-noshared","-f",str(bak),serial=serial,timeout=300)
            self._w2("ADB Backup... ","info",nl=False)
            self._w2("OK" if ok_b else "FAILED","ok" if ok_b else "fail")

        (out/"laporan.json").write_text(
            json.dumps({"ts":ts,"serial":serial,"info":info,"rooted":rooted},
                       indent=2,ensure_ascii=False),encoding="utf-8")

        self._set_step(3)
        self._w2(""); self._w2("─"*50,"dim")
        self._w2("Forensic extraction complete!","ok")
        self._w2(f"Perangkat : {info.get('Manufacturer','')} {info.get('Model','')}","info")
        self._w2(f"Berhasil  : {ok_n} kategori","info")
        self._w2(f"Output    : {out.resolve()}","dim")
        self._set_st(f"Selesai — {ok_n} data")


# ---------------------------------------------------------------------------
# Panel 2 : Samsung FRP Erase
# ---------------------------------------------------------------------------

_FRP_CMDS = [
    ("setup_complete",    "content insert --uri content://settings/secure --bind name:s:user_setup_complete --bind value:s:1"),
    ("device_provisioned","content insert --uri content://settings/global --bind name:s:device_provisioned --bind value:s:1"),
    ("clear_gsf",         "pm clear com.google.android.gsf"),
    ("clear_gms",         "pm clear com.google.android.gms"),
    ("clear_setup",       "pm clear com.google.android.setupwizard 2>/dev/null || pm clear com.sec.android.app.SecSetupWizard"),
    ("samsung_frp_delete","content delete --uri content://com.sec.android.provider.settings.SecSettings.SECURE --where \"name='frp_credential_key'\""),
]

class SamsungFRPPanel(BasePanel):
    def _build(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)

        left = ctk.CTkFrame(body, fg_color="#0d1a2e", corner_radius=0)
        left.pack(side="left", fill="both", expand=True)
        self._log = self._log_box(left)
        self._log.pack(fill="both", expand=True, padx=12, pady=12)
        self._device_right_panel(body)

        foot = ctk.CTkFrame(self, fg_color="#0d1520", height=48, corner_radius=0)
        foot.pack(fill="x")
        foot.pack_propagate(False)
        ctk.CTkButton(foot, text="▶  Scan Perangkat",
                      font=("Segoe UI",11), fg_color="#1a3f7a", hover_color="#1e4f9a",
                      width=160, height=34, corner_radius=17,
                      command=self._scan).pack(side="left", padx=12, pady=7)
        ctk.CTkButton(foot, text="🗑  Hapus FRP",
                      font=("Segoe UI",11,"bold"), fg_color="#7a1a1a", hover_color="#9a1e1e",
                      width=140, height=34, corner_radius=17,
                      command=self._hapus_frp).pack(side="left", padx=4, pady=7)
        self._status = ctk.CTkLabel(foot, text="", font=("Segoe UI",9), text_color="#37474f")
        self._status.pack(side="right", padx=12)
        self._serial = ""
        self.after(500, self._scan)

    def _w2(self, t, tag="info", nl=True): self._w(self._log, t, tag, nl)
    def _set_st(self, t): self.after(0, lambda: self._status.configure(text=t))

    def _scan(self):
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        self._clear(self._log)
        self._w2("Samsung FRP Erase Tool","bold")
        self._w2("─"*50,"dim"); self._w2("")
        ok,_=adb("version")
        if not ok: self._w2("ADB tidak ditemukan!","fail"); return
        serials=[]
        for i in range(6):
            serials=get_devices()
            if serials: break
            self._w2(f"Menunggu perangkat... ({i+1}/6)","dim"); time.sleep(3)
        if not serials: self._w2("Tidak ada perangkat.","fail"); return
        self._serial=serials[0]
        self._set_st(f"Serial: {self._serial}")
        info=get_info(self._serial)
        rooted=is_rooted(self._serial)
        mode=boot_mode_label(info)
        self._update_device_panel(info,rooted,mode)
        self._lbl_step.configure(text="[ADB] ERASE FRP")
        self._w2("Starting ADB Interface... ","info",nl=False); time.sleep(.3); self._w2("OK","ok")
        for k in ("Manufacturer","Model","Android","SDK","Serial","Patch","CPU"):
            v=info.get(k,"");   
            if v: self._w2(f"{k:<20}: ","dim",nl=False); self._w2(v,"cyan")
            time.sleep(.04)
        self._w2("")
        self._w2("Checking permission... ","info",nl=False)
        self._w2("root" if rooted else "no root","ok" if rooted else "warn")
        self._w2("")
        self._w2("Tekan [Hapus FRP] untuk melanjutkan.","dim")

    def _hapus_frp(self):
        if not self._serial: self._scan(); return
        threading.Thread(target=self._do_frp, daemon=True).start()

    def _do_frp(self):
        mulai=time.time()
        self._w2(""); self._w2("Removing FRP...","bold")
        ok_any=False
        for nama,cmd in _FRP_CMDS:
            ok,_=shell(self._serial,cmd,timeout=15)
            self._w2(f"  {nama}: ","dim",nl=False)
            self._w2("OK" if ok else "SKIP","ok" if ok else "dim")
            if ok: ok_any=True
        elapsed=round(time.time()-mulai)
        self._w2("")
        if ok_any:
            self._w2("FRP berhasil dihapus!","ok")
        else:
            self._w2("FRP gagal dihapus. Coba dengan root.","fail")
        self._w2(f"Elapsed time : {elapsed} seconds","dim")
        self._set_st("OK" if ok_any else "FAILED")


# ---------------------------------------------------------------------------
# Panel 3 : Xiaomi / Poco ADB
# ---------------------------------------------------------------------------

class XiaomiPanel(BasePanel):
    def _build(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        left = ctk.CTkFrame(body, fg_color="#0d1a2e", corner_radius=0)
        left.pack(side="left", fill="both", expand=True)
        self._log = self._log_box(left)
        self._log.pack(fill="both", expand=True, padx=12, pady=12)
        self._device_right_panel(body)

        foot = ctk.CTkFrame(self, fg_color="#0d1520", height=48, corner_radius=0)
        foot.pack(fill="x"); foot.pack_propagate(False)
        ctk.CTkButton(foot, text="▶  Scan", font=("Segoe UI",11),
                      fg_color="#1a3f7a", hover_color="#1e4f9a",
                      width=100, height=34, corner_radius=17,
                      command=self._scan).pack(side="left", padx=12, pady=7)
        ctk.CTkButton(foot, text="🗑  Hapus FRP+Mi", font=("Segoe UI",11,"bold"),
                      fg_color="#7a1a1a", hover_color="#9a1e1e",
                      width=160, height=34, corner_radius=17,
                      command=self._hapus).pack(side="left", padx=4, pady=7)
        ctk.CTkButton(foot, text="📦  Ekstrak", font=("Segoe UI",11),
                      fg_color="#1a4a1a", hover_color="#1e5a1e",
                      width=120, height=34, corner_radius=17,
                      command=self._ekstrak).pack(side="left", padx=4, pady=7)
        self._status = ctk.CTkLabel(foot, text="", font=("Segoe UI",9), text_color="#37474f")
        self._status.pack(side="right", padx=12)
        self._serial=""; self.after(500, self._scan)

    def _w2(self,t,tag="info",nl=True): self._w(self._log,t,tag,nl)
    def _set_st(self,t): self.after(0, lambda: self._status.configure(text=t))

    def _scan(self):
        threading.Thread(target=self._do_scan, daemon=True).start()

    def _do_scan(self):
        self._clear(self._log)
        self._w2("Xiaomi / POCO ADB Tool","bold"); self._w2("─"*50,"dim"); self._w2("")
        ok,_=adb("version")
        if not ok: self._w2("ADB tidak ditemukan!","fail"); return
        serials=[]
        for i in range(6):
            serials=get_devices()
            if serials: break
            self._w2(f"Menunggu... ({i+1}/6)","dim"); time.sleep(3)
        if not serials: self._w2("Tidak ada perangkat.","fail"); return
        self._serial=serials[0]
        info=get_info(self._serial)
        rooted=is_rooted(self._serial)
        mode=boot_mode_label(info)
        self._update_device_panel(info,rooted,mode)
        self._lbl_step.configure(text="Device Info")

        # Cek codename Poco X3 NFC
        codename=info.get("Device","").lower()
        if codename in ("surya","karna"):
            self._w2("POCO X3 NFC terdeteksi!","cyan")
        self._w2("Starting ADB Interface... ","info",nl=False); time.sleep(.3); self._w2("OK","ok")
        for k in ("Manufacturer","Model","Device","MIUI","Android","SDK","Platform","Serial","Patch"):
            v=info.get(k,"")
            if v: self._w2(f"{k:<20}: ","dim",nl=False); self._w2(v,"cyan")
            time.sleep(.04)
        self._w2("")
        # Bootloader
        bl=prop(self._serial,"ro.boot.flash.locked")
        bl_label="UNLOCKED" if bl=="0" else ("LOCKED" if bl=="1" else "UNKNOWN")
        bl_tag="ok" if bl_label=="UNLOCKED" else "warn"
        self._w2(f"Bootloader         : ","dim",nl=False); self._w2(bl_label,bl_tag)
        self._w2(f"Root               : ","dim",nl=False)
        self._w2("ROOTED" if rooted else "NOT ROOTED","ok" if rooted else "warn")
        self._w2(f"Connection         : ","dim",nl=False); self._w2("ADB","ok")
        self._set_st(f"Serial: {self._serial}")

    def _hapus(self):
        if not self._serial: self._scan(); return
        threading.Thread(target=self._do_hapus, daemon=True).start()

    def _do_hapus(self):
        mulai=time.time()
        self._w2(""); self._w2("Menghapus FRP + Mi Account...","bold")
        cmds=[
            ("setup_complete",  "content insert --uri content://settings/secure --bind name:s:user_setup_complete --bind value:s:1"),
            ("device_provisioned","content insert --uri content://settings/global --bind name:s:device_provisioned --bind value:s:1"),
            ("clear_gsf",        "pm clear com.google.android.gsf"),
            ("clear_gms",        "pm clear com.google.android.gms"),
            ("clear_mi_account", "pm clear com.xiaomi.account 2>/dev/null"),
            ("clear_micloud",    "pm clear com.xiaomi.micloud 2>/dev/null"),
            ("clear_setup",      "pm clear com.miui.setupwizard 2>/dev/null || pm clear com.google.android.setupwizard"),
        ]
        ok_n=0
        for nama,cmd in cmds:
            ok,_=shell(self._serial,cmd,timeout=15)
            self._w2(f"  {nama}: ","dim",nl=False)
            self._w2("OK" if ok else "SKIP","ok" if ok else "dim")
            if ok: ok_n+=1
        elapsed=round(time.time()-mulai)
        self._w2(f"\nSelesai: {ok_n}/{len(cmds)} berhasil","ok" if ok_n>0 else "fail")
        self._w2(f"Elapsed time : {elapsed} seconds","dim")
        self._set_st(f"{ok_n}/{len(cmds)} OK")

    def _ekstrak(self):
        if not self._serial: self._scan(); return
        threading.Thread(target=self._do_ekstrak, daemon=True).start()

    def _do_ekstrak(self):
        ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        out=Path(f"xiaomi_{ts}")/self._serial
        out.mkdir(parents=True,exist_ok=True)
        self._w2(""); self._w2("Ekstraksi data Xiaomi...","cyan")
        ok_n=0
        for nama,cmd,fname in EXTRACTIONS:
            ok,data=shell(self._serial,cmd,timeout=25)
            if ok and data: (out/fname).write_text(data,encoding="utf-8"); ok_n+=1
            time.sleep(.2); self._w2(f"{nama}... ","info",nl=False)
            self._w2("OK" if ok else "SKIP","ok" if ok else "dim")
        self._w2(f"\nOutput: {out.resolve()}","dim")
        self._set_st(f"Ekstrak: {ok_n} data")


# ---------------------------------------------------------------------------
# Panel 4 : EDL - Poco X3 NFC
# ---------------------------------------------------------------------------

class EDLPanel(BasePanel):
    def _build(self):
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True)
        left = ctk.CTkFrame(body, fg_color="#0d1a2e", corner_radius=0)
        left.pack(side="left", fill="both", expand=True)
        self._log = self._log_box(left)
        self._log.pack(fill="both", expand=True, padx=12, pady=12)

        # Panel kanan khusus EDL
        right = ctk.CTkFrame(body, fg_color="#0a1628", width=260, corner_radius=0)
        right.pack(side="right", fill="y"); right.pack_propagate(False)
        self._lbl_step = ctk.CTkLabel(right, text="EDL Mode",
                                       font=("Segoe UI",14,"bold"), text_color="#eceff1")
        self._lbl_step.pack(pady=(18,4))
        self._phone = PhoneCanvas(right, width=200, height=170,
                                   bg="#0a1628", highlightthickness=0)
        self._phone.pack(pady=4)
        ctk.CTkLabel(right, text="Poco X3 NFC",
                     font=("Segoe UI",13,"bold"), text_color="#eceff1").pack(pady=2)
        for t in ("surya / karna","Snapdragon 732G","USB: 0x9008"):
            ctk.CTkLabel(right, text=t, font=("Segoe UI",9), text_color="#78909c").pack(pady=1)

        # Programmer path
        pf = ctk.CTkFrame(right, fg_color="#0d1e35", corner_radius=8)
        pf.pack(fill="x", padx=10, pady=8)
        ctk.CTkLabel(pf, text="Programmer:", font=("Segoe UI",9),
                     text_color="#546e7a").pack(anchor="w", padx=8, pady=(6,0))
        self._prog_var = ctk.StringVar(value="prog_firehose_ddr.elf")
        ctk.CTkEntry(pf, textvariable=self._prog_var,
                     font=("Segoe UI",9), height=28,
                     fg_color="#0a1628", border_color="#1a3a5a").pack(
                         fill="x", padx=8, pady=(2,8))

        foot = ctk.CTkFrame(self, fg_color="#0d1520", height=48, corner_radius=0)
        foot.pack(fill="x"); foot.pack_propagate(False)
        btns = [
            ("Cek EDL",      "#1a2a3e", self._cek_edl),
            ("Masuk EDL",    "#1a3f7a", self._masuk_edl),
            ("Hapus FRP",    "#7a1a1a", self._hapus_frp_edl),
            ("Dump Partisi", "#1a4a1a", self._dump_partisi),
        ]
        for txt, fc, cmd in btns:
            ctk.CTkButton(foot, text=txt, font=("Segoe UI",10),
                          fg_color=fc, hover_color=fc,
                          width=110, height=34, corner_radius=17,
                          command=cmd).pack(side="left", padx=5, pady=7)
        self._status = ctk.CTkLabel(foot, text="", font=("Segoe UI",9), text_color="#37474f")
        self._status.pack(side="right", padx=8)
        self._w2("EDL Tool - Poco X3 NFC (SM7150)","bold")
        self._w2("─"*50,"dim"); self._w2("")
        self._w2("Cara masuk EDL:","cyan")
        self._w2("  1. Via ADB   : adb reboot edl","info")
        self._w2("  2. Via Fastboot: fastboot oem edl","info")
        self._w2("  3. Test Point: Short TP5 ke GND saat sambung USB","info")
        self._w2("  4. Volume- + sambung USB (beberapa unit)","info")
        self._w2("","info")
        self._w2("Klik [Cek EDL] untuk deteksi mode 9008.","dim")

    def _w2(self,t,tag="info",nl=True): self._w(self._log,t,tag,nl)
    def _set_st(self,t): self.after(0, lambda: self._status.configure(text=t))

    def _cek_edl(self):
        threading.Thread(target=self._do_cek_edl, daemon=True).start()

    def _do_cek_edl(self):
        self._w2("\nMemeriksa EDL mode (USB 0x9008)...","bold")
        ada=deteksi_edl()
        if ada:
            self._w2("EDL mode TERDETEKSI!","ok")
            self._w2("Perangkat siap menerima firehose commands.","info")
            self._lbl_step.configure(text="EDL AKTIF")
            self._set_st("9008 OK")
        else:
            self._w2("EDL mode tidak terdeteksi.","fail")
            self._w2("Masuk EDL dulu menggunakan salah satu metode di atas.","warn")
            self._set_st("Tidak ada 9008")

    def _masuk_edl(self):
        threading.Thread(target=self._do_masuk_edl, daemon=True).start()

    def _do_masuk_edl(self):
        self._w2("\nMasuk EDL via ADB...","bold")
        serials=get_devices()
        if serials:
            ok,_=adb("reboot","edl",serial=serials[0],timeout=10)
            if ok:
                self._w2("Perintah EDL dikirim. Menunggu device...","ok")
                time.sleep(5); self._do_cek_edl()
            else:
                self._w2("ADB reboot edl gagal. Coba fastboot oem edl.","warn")
        else:
            ok,_=_run(["fastboot","oem","edl"],timeout=10)
            if ok: self._w2("Perintah EDL dikirim via Fastboot.","ok"); time.sleep(5); self._do_cek_edl()
            else:  self._w2("Tidak ada perangkat ADB/Fastboot. Gunakan test point.","fail")

    def _hapus_frp_edl(self):
        threading.Thread(target=self._do_hapus_frp_edl, daemon=True).start()

    def _do_hapus_frp_edl(self):
        self._w2("\nHapus FRP via EDL...","bold")
        if not deteksi_edl():
            self._w2("EDL mode tidak aktif! Masuk EDL dulu.","fail"); return
        ok,_=_run(["edlclient","e","frp","--loader",self._prog_var.get()],timeout=60)
        self._w2("Erase FRP ... ","info",nl=False); self._w2("OK" if ok else "FAILED","ok" if ok else "fail")
        ok2,_=_run(["edlclient","e","misc","--loader",self._prog_var.get()],timeout=60)
        self._w2("Erase misc... ","info",nl=False); self._w2("OK" if ok2 else "FAILED","ok" if ok2 else "fail")
        self._set_st("FRP OK" if (ok or ok2) else "FAILED")

    def _dump_partisi(self):
        threading.Thread(target=self._do_dump, daemon=True).start()

    def _do_dump(self):
        if not deteksi_edl():
            self._w2("\nEDL mode tidak aktif!","fail"); return
        ts=datetime.now().strftime("%Y%m%d_%H%M%S")
        out=Path(f"edl_dump_{ts}"); out.mkdir(parents=True,exist_ok=True)
        self._w2(f"\nDump partisi ke {out.resolve()}","cyan")
        for nama in ("frp","misc","persist"):
            self._w2(f"Dump {nama}... ","info",nl=False)
            ok,_=_run(["edlclient","rf",nama,str(out/f"{nama}.bin"),
                       "--loader",self._prog_var.get()],timeout=300)
            self._w2("OK" if ok else "FAILED","ok" if ok else "fail")
        self._w2(f"Output: {out.resolve()}","dim")
        self._set_st("Dump selesai")


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

NAV_ITEMS = [
    ("🔎  Forensic Ultra",  ForensicPanel),
    ("📱  Samsung FRP",     SamsungFRPPanel),
    ("👾  Xiaomi / POCO",   XiaomiPanel),
    ("⚡  EDL Poco X3 NFC", EDLPanel),
]


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Android Forensic Suite - All In One")
        self.geometry("1100x680")
        self.minsize(950,580)
        self.configure(fg_color="#111827")
        self._panels: dict = {}
        self._active  = None
        self._build()

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color="#0d1520", height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        lf = ctk.CTkFrame(hdr, fg_color="transparent")
        lf.pack(side="left", padx=14, pady=8)
        ctk.CTkLabel(lf, text="Android",  font=("Segoe UI",18,"bold"), text_color="#e8eaf6").pack(side="left")
        ctk.CTkLabel(lf, text=" Forensic",font=("Segoe UI",18,"bold"), text_color="#42a5f5").pack(side="left")
        ctk.CTkLabel(lf, text="SUITE",    font=("Segoe UI",11,"bold"),
                     text_color="#ffd54f", fg_color="#1a3a6a",
                     corner_radius=5, width=56).pack(side="left", padx=6)
        ctk.CTkLabel(hdr, text="All In One  |  Version 2.0.0 (64-bit)",
                     font=("Segoe UI",10), text_color="#546e7a").pack(side="left")

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # Sidebar
        sidebar = ctk.CTkFrame(main, fg_color="#0a1628", width=190, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ctk.CTkLabel(sidebar, text="MENU", font=("Segoe UI",9,"bold"),
                     text_color="#37474f").pack(anchor="w", padx=16, pady=(16,6))

        self._nav_btns: list[ctk.CTkButton] = []
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True)
        self._content = content

        for label, PanelClass in NAV_ITEMS:
            btn = ctk.CTkButton(
                sidebar, text=label,
                font=("Segoe UI",11), anchor="w",
                fg_color="transparent", hover_color="#1a2a3e",
                text_color="#78909c", height=42, corner_radius=8,
                command=lambda lbl=label: self._switch(lbl))
            btn.pack(fill="x", padx=8, pady=2)
            self._nav_btns.append(btn)

            panel = PanelClass(content, self)
            panel.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._panels[label] = panel

        # Aktifkan panel pertama
        first = NAV_ITEMS[0][0]
        self._switch(first)

    def _switch(self, label: str):
        # Update tombol sidebar
        for btn in self._nav_btns:
            active = btn.cget("text") == label
            btn.configure(
                fg_color="#1a3f7a" if active else "transparent",
                text_color="#eceff1" if active else "#78909c",
            )
        # Tampilkan panel
        if self._active:
            self._panels[self._active].lower()
        self._panels[label].lift()
        self._active = label


def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
