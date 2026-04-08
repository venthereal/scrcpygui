#!/usr/bin/env python3
"""ScrcpyGUI Beta - CustomTkinter Light/WhiteSur + TCP/IP + Floating Toggle"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import subprocess, threading, os, json, time
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.expanduser("~/.config/scrcpy-gui/settings.json")

# ── WhiteSur Light Palette ─────────────────────────────────────────────────────
BG    = "#1c1c1e"
CARD  = "#2c2c2e"
CARD2 = "#3a3a3c"
BDR   = "#48484a"
ACC   = "#0a84ff"
RED   = "#ff453a"
YEL   = "#ffd60a"
GRN   = "#30d158"
TEXT  = "#ffffff"
DIM   = "#ebebf5"
FN    = "DejaVu Sans"
FNM   = "DejaVu Sans Mono"

MODES = ["Mirror Only", "Record", "Livestream"]
PLATFORM_RTMP = {
    "YouTube": "rtmp://a.rtmp.youtube.com/live2/",
    "Custom":  "",
}


def load_config():
    d = {
        "bitrate": "8M", "max_fps": "60", "resolution": "(default)",
        "codec": "h264", "rotation": "0", "mode": "Mirror Only",
        "record_path": os.path.expanduser("~/Videos/scrcpy"),
        "record_format": "mp4", "no_audio": False, "fullscreen": False,
        "borderless": False, "always_on_top": False, "stay_awake": True,
        "turn_screen_off": False, "no_control": False, "window_title": "scrcpy",
        "live_platform": "YouTube", "live_key": "", "live_bitrate": "3000k",
        "live_resolution": "1280x720", "live_fps": "30",
        "show_floating": True, "tcpip_port": "5555",
    }
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE) as f:
                d.update(json.load(f))
    except Exception:
        pass
    return d


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"save error: {e}")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg          = load_config()
        self.process      = None
        self.ffmpeg_proc  = None
        self.running      = False
        self.live_running = False
        self.key_visible  = False

        self.title("ScrcpyGUI")
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.minsize(960, 660)
        W, H = 1020, 740
        self.geometry(f"{W}x{H}+{(self.winfo_screenwidth()-W)//2}+{(self.winfo_screenheight()-H)//2}")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._setup_vars()
        self._build_ui()
        self._load_config()
        self._refresh_devices()
        self._build_floating()

    # ── Vars ──────────────────────────────────────────────────────────────────
    def _setup_vars(self):
        self.V = {
            "device":        tk.StringVar(),
            "bitrate":       tk.StringVar(value="8M"),
            "fps":           tk.StringVar(value="60"),
            "resolution":    tk.StringVar(value="(default)"),
            "codec":         tk.StringVar(value="h264"),
            "rotation":      tk.StringVar(value="0"),
            "mode":          tk.StringVar(value="Mirror Only"),
            "rec_path":      tk.StringVar(value=os.path.expanduser("~/Videos/scrcpy")),
            "rec_fmt":       tk.StringVar(value="mp4"),
            "no_audio":      tk.BooleanVar(value=False),
            "fullscreen":    tk.BooleanVar(value=False),
            "borderless":    tk.BooleanVar(value=False),
            "always_top":    tk.BooleanVar(value=False),
            "stay_awake":    tk.BooleanVar(value=True),
            "screen_off":    tk.BooleanVar(value=False),
            "view_only":     tk.BooleanVar(value=False),
            "win_title":     tk.StringVar(value="scrcpy"),
            "live_platform": tk.StringVar(value="YouTube"),
            "live_key":      tk.StringVar(value=""),
            "live_bitrate":  tk.StringVar(value="3000k"),
            "live_res":      tk.StringVar(value="1280x720"),
            "live_fps":      tk.StringVar(value="30"),
            "live_mic":      tk.BooleanVar(value=False),
            "show_floating": tk.BooleanVar(value=True),
            "tcpip_port":    tk.StringVar(value="5555"),
            "tcpip_host":    tk.StringVar(value=""),
        }
        for v in self.V.values():
            v.trace_add("write", lambda *_: self.after(20, self._preview))
        self.V["live_platform"].trace_add("write", lambda *_: self.after(20, self._update_rtmp_hint))
        self.V["mode"].trace_add("write", lambda *_: self.after(20, self._update_mode_ui))
        self.V["show_floating"].trace_add("write", lambda *_: self.after(20, self._toggle_floating_visibility))

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_devicebar()

        self.tabview = ctk.CTkTabview(
            self, fg_color=BG,
            segmented_button_fg_color=CARD,
            segmented_button_selected_color=ACC,
            segmented_button_selected_hover_color="#0060cc",
            segmented_button_unselected_color=CARD,
            segmented_button_unselected_hover_color=CARD2,
            text_color=DIM,
            border_color=BDR,
            border_width=1)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(8,0))

        for tab in ["📱  Mirror", "🔴  Livestream", "📶  TCP/IP", "⚙️  Settings", "📋  Log"]:
            self.tabview.add(tab)
            self.tabview.tab(tab).configure(fg_color=BG)

        self._build_tab_mirror()
        self._build_tab_live()
        self._build_tab_tcpip()
        self._build_tab_settings()
        self._build_tab_log()
        self._build_bottombar()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="ScrcpyGUI", font=ctk.CTkFont(FN,14,"bold"),
                     text_color=TEXT, fg_color=CARD).pack(side="left", padx=16)
        ctk.CTkLabel(hdr, text="Beta", font=ctk.CTkFont(FN,11),
                     text_color=DIM, fg_color=CARD).pack(side="left")

        self.lbl_status = ctk.CTkLabel(
            hdr, text="● Ready",
            font=ctk.CTkFont(FNM,10,"bold"),
            text_color=DIM, fg_color=CARD2,
            corner_radius=8, padx=12, pady=4)
        self.lbl_status.pack(side="right", padx=16, pady=10)

        ctk.CTkFrame(self, fg_color=BDR, height=1, corner_radius=0).pack(fill="x")

    # ── Device bar ────────────────────────────────────────────────────────────
    def _build_devicebar(self):
        bar = ctk.CTkFrame(self, fg_color=BG)
        bar.pack(fill="x", padx=16, pady=(12,4))

        ctk.CTkLabel(bar, text="DEVICE", font=ctk.CTkFont(FN,9,"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left", padx=(0,8))

        self.combo_device = ctk.CTkComboBox(
            bar, values=[], variable=self.V["device"],
            width=320, font=ctk.CTkFont(FNM,10),
            fg_color=CARD, border_color=BDR, button_color=ACC,
            dropdown_fg_color=CARD, dropdown_text_color=TEXT,
            text_color=TEXT, state="readonly")
        self.combo_device.pack(side="left", padx=(0,8))

        ctk.CTkButton(bar, text="↺  Refresh", command=self._refresh_devices,
                      width=110, height=32, fg_color=CARD, hover_color=CARD2,
                      text_color=ACC, font=ctk.CTkFont(FN,10,"bold"),
                      border_width=1, border_color=BDR, corner_radius=8
                      ).pack(side="left", padx=(0,8))

        self.lbl_device_info = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(FN,9),
                                      text_color=DIM, fg_color=BG)
        self.lbl_device_info.pack(side="left")

    # ── Tab Mirror ────────────────────────────────────────────────────────────
    def _build_tab_mirror(self):
        tab = self.tabview.tab("📱  Mirror")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        self._section(left, "VIDEO SETTINGS")
        for label, vals, key, unit in [
            ("Bit rate",       ["1M","2M","4M","6M","8M","10M","12M","16M","20M","25M"], "bitrate",    "Mbps"),
            ("Max FPS",        ["15","24","30","45","60","90","120"],                     "fps",        "fps"),
            ("Max resolution", ["(default)","480","720","1080","1280","1440","1920"],     "resolution", "px"),
            ("Codec",          ["h264","h265","av1"],                                     "codec",      ""),
            ("Rotation",       ["0","90","180","270"],                                    "rotation",   "°"),
        ]:
            row = ctk.CTkFrame(left, fg_color=BG)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=150, anchor="w",
                         font=ctk.CTkFont(FN,10), text_color=DIM,
                         fg_color=BG).pack(side="left")
            self._combo_ctk(row, vals, self.V[key], 120).pack(side="left", padx=(0,6))
            if unit:
                ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(FN,9),
                             text_color=DIM, fg_color=BG).pack(side="left")

        self._section(left, "OUTPUT MODE")
        row = ctk.CTkFrame(left, fg_color=BG)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Mode", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        self._combo_ctk(row, MODES, self.V["mode"], 160).pack(side="left")

        self.frame_mode = ctk.CTkFrame(left, fg_color=BG)
        self.frame_mode.pack(fill="x", pady=(4,0))

        # Display options
        self._section(right, "DISPLAY OPTIONS")
        options = [
            ("No audio",        "no_audio"),
            ("Fullscreen",      "fullscreen"),
            ("Borderless",      "borderless"),
            ("Always on top",   "always_top"),
            ("Stay awake",      "stay_awake"),
            ("Turn screen off", "screen_off"),
            ("View only",       "view_only"),
        ]
        grid = ctk.CTkFrame(right, fg_color=BG)
        grid.pack(fill="x", pady=4)
        for i, (teks, key) in enumerate(options):
            col = i % 2
            row_i = i // 2
            ctk.CTkCheckBox(
                grid, text=teks, variable=self.V[key],
                font=ctk.CTkFont(FN,10), text_color=TEXT,
                fg_color=ACC, hover_color="#0060cc",
                checkmark_color=TEXT, border_color=BDR,
                width=20, height=20,
                command=lambda: self.after(20, self._preview)
            ).grid(row=row_i, column=col, sticky="w", padx=(0,20), pady=5)

        self._section(right, "WINDOW")
        row = ctk.CTkFrame(right, fg_color=BG)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Window title", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.V["win_title"], width=180,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,10)).pack(side="left")

        self._section(right, "COMMAND PREVIEW")
        self.txt_cmd = ctk.CTkTextbox(
            right, height=80, fg_color=CARD2, text_color=ACC,
            font=ctk.CTkFont(FNM,9), border_color=BDR,
            border_width=1, wrap="word")
        self.txt_cmd.pack(fill="x")
        self.txt_cmd.configure(state="disabled")

    # ── Tab Live ──────────────────────────────────────────────────────────────
    def _build_tab_live(self):
        tab = self.tabview.tab("🔴  Livestream")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        self._section(left, "PLATFORM & STREAM KEY")

        row = ctk.CTkFrame(left, fg_color=BG)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Platform", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        self._combo_ctk(row, list(PLATFORM_RTMP.keys()),
                        self.V["live_platform"], 140).pack(side="left")

        ctk.CTkLabel(left, text="Stream Key",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(anchor="w", pady=(10,2))

        self.entry_stream_key = ctk.CTkEntry(
            left, textvariable=self.V["live_key"],
            show="•", fg_color=CARD, border_color=BDR,
            text_color=TEXT, font=ctk.CTkFont(FNM,10))
        self.entry_stream_key.pack(fill="x", pady=(0,4))

        self.btn_toggle_key = ctk.CTkButton(
            left, text="👁  Show Key",
            command=self._toggle_key_visibility,
            width=120, height=28, fg_color=CARD2, hover_color=BDR,
            text_color=DIM, font=ctk.CTkFont(FN,9), corner_radius=6,
            border_width=1, border_color=BDR)
        self.btn_toggle_key.pack(anchor="w", pady=(0,4))

        self.lbl_rtmp = ctk.CTkLabel(
            left, text="", font=ctk.CTkFont(FN,8),
            text_color=DIM, fg_color=BG,
            wraplength=340, justify="left")
        self.lbl_rtmp.pack(anchor="w", pady=(2,0))

        self._section(left, "STREAM QUALITY")
        for label, vals, key, unit in [
            ("Video bitrate", ["1000k","1500k","2000k","2500k","3000k","4000k","5000k","6000k"], "live_bitrate", "bps"),
            ("Resolution",    ["854x480","1280x720","1920x1080"],                                "live_res",     ""),
            ("Stream FPS",    ["24","25","30","48","60"],                                        "live_fps",     "fps"),
        ]:
            row = ctk.CTkFrame(left, fg_color=BG)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=label, width=150, anchor="w",
                         font=ctk.CTkFont(FN,10), text_color=DIM,
                         fg_color=BG).pack(side="left")
            self._combo_ctk(row, vals, self.V[key], 130).pack(side="left", padx=(0,6))
            if unit:
                ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(FN,9),
                             text_color=DIM, fg_color=BG).pack(side="left")

        ctk.CTkCheckBox(
            left, text="🎙  Enable Microphone",
            variable=self.V["live_mic"],
            font=ctk.CTkFont(FN,10), text_color=TEXT,
            fg_color=ACC, hover_color="#0060cc",
            checkmark_color=TEXT, border_color=BDR,
            width=20, height=20,
            command=lambda: self.after(20, self._preview)
        ).pack(anchor="w", pady=(12,0))

        self._section(right, "FULL COMMAND PREVIEW")
        self.txt_cmd_live = ctk.CTkTextbox(
            right, height=220, fg_color=CARD, text_color=ACC,
            font=ctk.CTkFont(FNM,9), border_color=BDR,
            border_width=1, wrap="word")
        self.txt_cmd_live.pack(fill="x")
        self.txt_cmd_live.configure(state="disabled")

    # ── Tab TCP/IP ────────────────────────────────────────────────────────────
    def _build_tab_tcpip(self):
        tab = self.tabview.tab("📶  TCP/IP")

        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        # ── Connect via WiFi ──
        self._section(left, "CONNECT VIA WIFI")

        info_frame = ctk.CTkFrame(left, fg_color=CARD, corner_radius=10,
                                  border_width=1, border_color=BDR)
        info_frame.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(info_frame,
                     text="Connect phone via USB first, then enable TCP/IP.\nAfter that you can disconnect USB and use WiFi.",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=CARD, justify="left",
                     padx=12, pady=8).pack(anchor="w")

        # Port
        row = ctk.CTkFrame(left, fg_color=BG)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Port", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.V["tcpip_port"], width=100,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,10)).pack(side="left")
        ctk.CTkLabel(row, text="(default: 5555)", font=ctk.CTkFont(FN,9),
                     text_color=DIM, fg_color=BG).pack(side="left", padx=8)

        # Step 1 button
        ctk.CTkButton(left, text="Step 1: Enable TCP/IP (USB required)",
                      command=self._enable_tcpip,
                      height=38, fg_color=ACC, hover_color="#0060cc",
                      text_color="white", font=ctk.CTkFont(FN,11,"bold"),
                      corner_radius=8).pack(fill="x", pady=(8,4))

        # Host IP
        row2 = ctk.CTkFrame(left, fg_color=BG)
        row2.pack(fill="x", pady=(12,4))
        ctk.CTkLabel(row2, text="Device IP", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.V["tcpip_host"], width=180,
                     placeholder_text="e.g. 192.168.1.100",
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,10)).pack(side="left")

        ctk.CTkButton(left, text="Step 2: Connect via WiFi",
                      command=self._connect_wifi,
                      height=38, fg_color=GRN, hover_color="#28a745",
                      text_color="white", font=ctk.CTkFont(FN,11,"bold"),
                      corner_radius=8).pack(fill="x", pady=4)

        # ── Back to USB ──
        self._section(left, "BACK TO USB")
        ctk.CTkButton(left, text="Disconnect WiFi & Switch to USB",
                      command=self._disconnect_wifi,
                      height=38, fg_color=CARD2, hover_color=BDR,
                      text_color=TEXT, font=ctk.CTkFont(FN,11),
                      border_width=1, border_color=BDR,
                      corner_radius=8).pack(fill="x", pady=4)

        # ── Status / Log TCP ──
        self._section(right, "TCP/IP LOG")
        self.txt_tcpip = ctk.CTkTextbox(
            right, height=300, fg_color=CARD, text_color=TEXT,
            font=ctk.CTkFont(FNM,9), border_color=BDR,
            border_width=1, wrap="word")
        self.txt_tcpip.pack(fill="both", expand=True)
        self.txt_tcpip.configure(state="disabled")
        self.txt_tcpip._textbox.tag_configure("ok",    foreground=GRN)
        self.txt_tcpip._textbox.tag_configure("error", foreground=RED)
        self.txt_tcpip._textbox.tag_configure("info",  foreground=ACC)

    def _log_tcpip(self, text, tag="info"):
        def _do():
            self.txt_tcpip.configure(state="normal")
            tb = self.txt_tcpip._textbox
            tb.configure(state="normal")
            tb.insert("end", text+"\n", tag)
            tb.see("end")
            tb.configure(state="disabled")
            self.txt_tcpip.configure(state="disabled")
        self.after(0, _do)

    def _enable_tcpip(self):
        port = self.V["tcpip_port"].get().strip() or "5555"
        self._log_tcpip(f"$ adb tcpip {port}", "info")

        def _run():
            try:
                r = subprocess.run(["adb","tcpip", port],
                                   capture_output=True, text=True, timeout=10)
                if r.returncode == 0:
                    self._log_tcpip(f"✓ TCP/IP enabled on port {port}", "ok")
                    self._log_tcpip("→ Now disconnect USB and enter device IP below", "info")
                else:
                    self._log_tcpip(f"Error: {r.stderr.strip()}", "error")
            except Exception as e:
                self._log_tcpip(f"Error: {e}", "error")

        threading.Thread(target=_run, daemon=True).start()

    def _connect_wifi(self):
        host = self.V["tcpip_host"].get().strip()
        port = self.V["tcpip_port"].get().strip() or "5555"
        if not host:
            messagebox.showwarning("Missing IP", "Enter device IP address first!")
            return
        addr = f"{host}:{port}"
        self._log_tcpip(f"$ adb connect {addr}", "info")

        def _run():
            try:
                r = subprocess.run(["adb","connect", addr],
                                   capture_output=True, text=True, timeout=15)
                out = r.stdout.strip()
                if "connected" in out.lower():
                    self._log_tcpip(f"✓ {out}", "ok")
                    self._log_tcpip("→ Refresh device list in Mirror tab", "info")
                    self.after(500, self._refresh_devices)
                else:
                    self._log_tcpip(f"Failed: {out}", "error")
            except Exception as e:
                self._log_tcpip(f"Error: {e}", "error")

        threading.Thread(target=_run, daemon=True).start()

    def _disconnect_wifi(self):
        host = self.V["tcpip_host"].get().strip()
        port = self.V["tcpip_port"].get().strip() or "5555"
        addr = f"{host}:{port}" if host else ""
        cmd  = ["adb","disconnect"] + ([addr] if addr else [])
        self._log_tcpip(f"$ {' '.join(cmd)}", "info")

        def _run():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                self._log_tcpip(f"✓ {r.stdout.strip()}", "ok")
                self._log_tcpip("→ Reconnect USB cable if needed", "info")
                self.after(500, self._refresh_devices)
            except Exception as e:
                self._log_tcpip(f"Error: {e}", "error")

        threading.Thread(target=_run, daemon=True).start()

    # ── Tab Settings ──────────────────────────────────────────────────────────
    def _build_tab_settings(self):
        tab = self.tabview.tab("⚙️  Settings")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        self._section(left, "TOOLS")

        # Floating toggle
        row = ctk.CTkFrame(left, fg_color=BG)
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text="Floating Widget", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=TEXT,
                     fg_color=BG).pack(side="left")
        ctk.CTkSwitch(
            row, text="Show",
            variable=self.V["show_floating"],
            font=ctk.CTkFont(FN,10), text_color=DIM,
            fg_color=BDR, progress_color=ACC,
            button_color=CARD, button_hover_color=CARD2
        ).pack(side="left")

        self._section(left, "PRESET")
        for txt, cmd in [
            ("💾  Save Preset",    self._save),
            ("📋  Copy Command",   self._copy_cmd),
            ("🔄  Reset Default",  self._reset_config),
        ]:
            ctk.CTkButton(left, text=txt, command=cmd,
                          height=36, fg_color=CARD, hover_color=CARD2,
                          text_color=TEXT, font=ctk.CTkFont(FN,10),
                          border_width=1, border_color=BDR,
                          corner_radius=8, anchor="w"
                          ).pack(fill="x", pady=3)

        self._section(right, "ABOUT")
        af = ctk.CTkFrame(right, fg_color=CARD, corner_radius=10,
                          border_width=1, border_color=BDR)
        af.pack(fill="x", pady=4)
        # Header
        ctk.CTkLabel(af, text="ScrcpyGUI",
                     font=ctk.CTkFont(FN,16,"bold"),
                     text_color=TEXT, fg_color=CARD,
                     padx=14, pady=10).pack(anchor="w")
        ctk.CTkLabel(af, text="Beta  ·  Built for Android Casting",
                     font=ctk.CTkFont(FN,9),
                     text_color=DIM, fg_color=CARD,
                     padx=14, pady=4).pack(anchor="w")

        ctk.CTkFrame(af, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", padx=14)

        ctk.CTkLabel(af, text="DEPENDENCIES",
                     font=ctk.CTkFont(FN,8,"bold"),
                     text_color=DIM, fg_color=CARD,
                     padx=14, pady=8).pack(anchor="w")

        deps = [
            ("scrcpy",      "3.3.4",   "Android screen cast"),
            ("ffmpeg",      "6.1.1",   "Stream encoder"),
            ("adb",         "latest",  "Android Debug Bridge"),
            ("xdotool",     "latest",  "Window detection"),
            ("PipeWire",    "system",  "Audio capture"),
            ("CustomTkinter","latest", "UI framework"),
        ]
        for name, ver, desc in deps:
            row = ctk.CTkFrame(af, fg_color=CARD)
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=f"  {name}",
                         font=ctk.CTkFont(FNM,10,"bold"),
                         text_color=ACC, fg_color=CARD,
                         width=120, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=ver,
                         font=ctk.CTkFont(FNM,9),
                         text_color=DIM, fg_color=CARD,
                         width=60, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=desc,
                         font=ctk.CTkFont(FN,9),
                         text_color=DIM, fg_color=CARD,
                         anchor="w").pack(side="left")

        ctk.CTkFrame(af, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", padx=14, pady=(8,0))
        ctk.CTkLabel(af, text=f"© {datetime.now().year}  VEN  —  All rights reserved",
                     font=ctk.CTkFont(FN,8),
                     text_color=DIM, fg_color=CARD,
                     padx=14, pady=8).pack(anchor="w")

    # ── Tab Log ───────────────────────────────────────────────────────────────
    def _build_tab_log(self):
        tab = self.tabview.tab("📋  Log")
        bar = ctk.CTkFrame(tab, fg_color=BG)
        bar.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(bar, text="ADB & FFMPEG LOG",
                     font=ctk.CTkFont(FN,9,"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkButton(bar, text="🗑  Clear", command=self._clear_log,
                      width=80, height=28, fg_color=CARD2, hover_color=BDR,
                      text_color=DIM, font=ctk.CTkFont(FN,9),
                      border_width=1, border_color=BDR,
                      corner_radius=6).pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            tab, fg_color=CARD, text_color="#555555",
            font=ctk.CTkFont(FNM,9),
            border_color=BDR, border_width=1, wrap="word")
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.configure(state="disabled")
        self.txt_log._textbox.tag_configure("error", foreground=RED)
        self.txt_log._textbox.tag_configure("ok",    foreground=GRN)
        self.txt_log._textbox.tag_configure("cmd",   foreground=YEL)
        self.txt_log._textbox.tag_configure("redup", foreground="#aaaaaa")

    def _clear_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("0.0","end")
        self.txt_log.configure(state="disabled")

    # ── Bottom bar ────────────────────────────────────────────────────────────
    def _build_bottombar(self):
        ctk.CTkFrame(self, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", side="bottom")
        bar = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=44)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        year = datetime.now().year
        self.lbl_statusbar = ctk.CTkLabel(
            bar, text=f"© {year}  VEN",
            font=ctk.CTkFont(FN,10,"bold"),
            text_color=DIM, fg_color=CARD)
        self.lbl_statusbar.pack(side="left", padx=12)

        self.btn_start = ctk.CTkButton(
            bar, text="▶   Start", command=self._toggle,
            width=140, height=32, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN,11,"bold"),
            corner_radius=8)
        self.btn_start.pack(side="right", padx=12, pady=6)

        for txt, cmd in [("Copy Command", self._copy_cmd), ("Save", self._save)]:
            ctk.CTkButton(bar, text=txt, command=cmd,
                          width=100 if txt=="Copy Command" else 70,
                          height=32, fg_color=CARD2, hover_color=BDR,
                          text_color=DIM, font=ctk.CTkFont(FN,9),
                          border_width=1, border_color=BDR,
                          corner_radius=8).pack(side="right", padx=4, pady=6)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color=BG)
        f.pack(fill="x", pady=(14,4))
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(FN,8,"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkFrame(f, fg_color=BDR, height=1, corner_radius=0).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _combo_ctk(self, parent, values, var, width=120):
        return ctk.CTkComboBox(
            parent, values=values, variable=var, width=width,
            font=ctk.CTkFont(FNM,10), fg_color=CARD,
            border_color=BDR, button_color=CARD2,
            button_hover_color=BDR, dropdown_fg_color=CARD,
            dropdown_text_color=TEXT, text_color=TEXT,
            state="readonly",
            command=lambda _: self.after(20, self._preview))

    def _toggle_key_visibility(self):
        self.key_visible = not self.key_visible
        self.entry_stream_key.configure(show="" if self.key_visible else "•")
        self.btn_toggle_key.configure(
            text="🔒 Hide Key" if self.key_visible else "👁  Show Key")

    def _toggle_floating_visibility(self):
        if not hasattr(self, "float_win"): return
        if self.V["show_floating"].get():
            self.float_win.deiconify()
        else:
            self.float_win.withdraw()

    def _update_rtmp_hint(self):
        if not hasattr(self,"lbl_rtmp"): return
        plat = self.V["live_platform"].get()
        base = PLATFORM_RTMP.get(plat,"")
        self.lbl_rtmp.configure(
            text=f"URL: {base}<KEY>" if base else "Enter full RTMP URL in Stream Key")

    def _update_mode_ui(self):
        for w in self.frame_mode.winfo_children():
            w.destroy()
        mode = self.V["mode"].get()
        if mode == "Record":
            self._ui_record(self.frame_mode)
        if not self.running:
            self.btn_start.configure(
                text="▶   Start Live" if mode=="Livestream" else "▶   Start")
        self.after(20, self._preview)

    def _ui_record(self, p):
        ctk.CTkLabel(p, text="Save folder",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(anchor="w", pady=(8,2))
        row = ctk.CTkFrame(p, fg_color=BG)
        row.pack(fill="x", pady=(0,4))
        ctk.CTkEntry(row, textvariable=self.V["rec_path"], width=240,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,10)).pack(side="left", padx=(0,6))
        ctk.CTkButton(row, text="…", command=self._pick_folder,
                      width=36, height=32, fg_color=CARD2, hover_color=BDR,
                      text_color=ACC, font=ctk.CTkFont(FN,12,"bold"),
                      corner_radius=6).pack(side="left")
        row2 = ctk.CTkFrame(p, fg_color=BG)
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Format", width=150, anchor="w",
                     font=ctk.CTkFont(FN,10), text_color=DIM,
                     fg_color=BG).pack(side="left")
        self._combo_ctk(row2, ["mp4","mkv"], self.V["rec_fmt"], 100).pack(side="left")

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_config(self):
        c = self.cfg
        self.V["bitrate"].set(c.get("bitrate","8M"))
        self.V["fps"].set(c.get("max_fps","60"))
        self.V["resolution"].set(c.get("resolution","(default)"))
        self.V["codec"].set(c.get("codec","h264"))
        self.V["rotation"].set(c.get("rotation","0"))
        self.V["mode"].set(c.get("mode","Mirror Only"))
        self.V["rec_path"].set(c.get("record_path",os.path.expanduser("~/Videos/scrcpy")))
        self.V["rec_fmt"].set(c.get("record_format","mp4"))
        self.V["no_audio"].set(c.get("no_audio",False))
        self.V["fullscreen"].set(c.get("fullscreen",False))
        self.V["borderless"].set(c.get("borderless",False))
        self.V["always_top"].set(c.get("always_on_top",False))
        self.V["stay_awake"].set(c.get("stay_awake",True))
        self.V["screen_off"].set(c.get("turn_screen_off",False))
        self.V["view_only"].set(c.get("no_control",False))
        self.V["win_title"].set(c.get("window_title","scrcpy"))
        self.V["live_platform"].set(c.get("live_platform","YouTube"))
        self.V["live_key"].set(c.get("live_key",""))
        self.V["live_bitrate"].set(c.get("live_bitrate","3000k"))
        self.V["live_res"].set(c.get("live_resolution","1280x720"))
        self.V["live_fps"].set(c.get("live_fps","30"))
        self.V["show_floating"].set(c.get("show_floating",True))
        self.V["tcpip_port"].set(c.get("tcpip_port","5555"))
        self._update_mode_ui()
        self._update_rtmp_hint()

    # ── ADB ───────────────────────────────────────────────────────────────────
    def _refresh_devices(self):
        self.combo_device.configure(values=["Scanning..."])
        self.V["device"].set("Scanning...")
        self.lbl_device_info.configure(text="")
        self._log("$ adb devices -l")
        threading.Thread(target=self._scan_adb, daemon=True).start()

    def _scan_adb(self):
        devices, lines = [], []
        try:
            r = subprocess.run(["adb","devices","-l"],
                               capture_output=True, text=True, timeout=8)
            raw = r.stdout.strip()
            lines.append(raw)
            for ln in raw.splitlines()[1:]:
                ln = ln.strip()
                if not ln: continue
                parts = ln.split()
                if len(parts) < 2: continue
                serial, status = parts[0], parts[1]
                if status == "device":
                    model = next((p.split(":")[1] for p in parts
                                  if p.startswith("model:")), "device")
                    icon = "📶" if "." in serial else "🔌"
                    devices.append(f"{serial}   [{model}] {icon}")
                elif status == "unauthorized":
                    devices.append(f"{serial}   [UNAUTHORIZED]")
                elif status == "offline":
                    devices.append(f"{serial}   [OFFLINE]")
        except FileNotFoundError:
            lines.append("ERROR: adb not found")
        except subprocess.TimeoutExpired:
            lines.append("ERROR: adb timeout")
        except Exception as e:
            lines.append(f"ERROR: {e}")
        self.after(0, lambda: self._set_devices(devices, "\n".join(lines)))

    def _set_devices(self, devices, log):
        self._log(log)
        if devices:
            self.combo_device.configure(values=devices)
            self.V["device"].set(devices[0])
            self.lbl_device_info.configure(text=f"✓ {len(devices)} device(s)", text_color=GRN)
        else:
            self.combo_device.configure(values=["(no devices)"])
            self.V["device"].set("(no devices)")
            self.lbl_device_info.configure(text="Connect phone + enable USB Debugging", text_color=YEL)

    # ── Build command ─────────────────────────────────────────────────────────
    def _build_cmd(self, force_always_on_top=False):
        mode = self.V["mode"].get()
        cmd  = ["scrcpy"]
        dev  = self.V["device"].get()
        if dev and "no devices" not in dev and "Scanning" not in dev:
            cmd += ["-s", dev.split()[0]]
        cmd += ["--video-bit-rate", self.V["bitrate"].get()]
        cmd += ["--max-fps",        self.V["fps"].get()]
        res = self.V["resolution"].get()
        if res and res != "(default)":
            cmd += ["--max-size", res]
        if self.V["codec"].get() != "h264":
            cmd += ["--video-codec", self.V["codec"].get()]
        if self.V["rotation"].get() != "0":
            cmd += ["--rotation", self.V["rotation"].get()]
        if mode == "Record":
            path = self.V["rec_path"].get()
            fmt  = self.V["rec_fmt"].get() or "mp4"
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(path, exist_ok=True)
            cmd += ["--record", os.path.join(path, f"rec_{ts}.{fmt}")]
        if self.V["no_audio"].get():    cmd += ["--no-audio"]
        if self.V["fullscreen"].get() and not force_always_on_top:
            cmd += ["--fullscreen"]
        if self.V["borderless"].get():  cmd += ["--window-borderless"]
        if self.V["always_top"].get() or force_always_on_top:
            cmd += ["--always-on-top"]
        if force_always_on_top:
            cmd += ["--fullscreen"]
        if self.V["stay_awake"].get() and not self.V["view_only"].get():
            cmd += ["--stay-awake"]
        if self.V["screen_off"].get():  cmd += ["--turn-screen-off"]
        if self.V["view_only"].get():   cmd += ["--no-control"]
        j = self.V["win_title"].get()
        if j and j != "scrcpy":
            cmd += ["--window-title", j]
        return cmd

    def _preview(self):
        try:
            mode = self.V["mode"].get()
            if mode == "Livestream":
                plat = self.V["live_platform"].get()
                base = PLATFORM_RTMP.get(plat,"")
                rtmp = base+"<KEY>" if base else "<RTMP_URL>"
                br   = self.V["live_bitrate"].get()
                fps  = self.V["live_fps"].get()
                teks = (f"scrcpy --always-on-top --fullscreen [...]\n"
                        f"ffmpeg -f x11grab -draw_mouse 0 -r {fps}\n"
                        f"  -f pulse -i monitor -c:v libx264\n"
                        f"  -b:v {br} -c:a aac -f flv {rtmp}")
                self._upd(self.txt_cmd_live, teks)
            self._upd(self.txt_cmd, " ".join(self._build_cmd()))
        except Exception:
            pass

    def _upd(self, w, t):
        w.configure(state="normal")
        w.delete("0.0","end")
        w.insert("0.0", t)
        w.configure(state="disabled")

    def _log(self, teks):
        def _do():
            self.txt_log.configure(state="normal")
            tb = self.txt_log._textbox
            tb.configure(state="normal")
            for brs in (teks+"\n").splitlines():
                bl = brs.lower()
                if brs.strip().startswith("$"):   tag = "cmd"
                elif any(w in bl for w in ["error","fail","cannot"]): tag = "error"
                elif any(w in bl for w in ["✓","→","found","live","start"]): tag = "ok"
                else: tag = "redup"
                tb.insert("end", brs+"\n", tag)
                tb.see("end")
            tb.configure(state="disabled")
            self.txt_log.configure(state="disabled")
        self.after(0, _do)

    # ── Toggle ────────────────────────────────────────────────────────────────
    def _toggle(self):
        if self.running or self.live_running:
            self._stop()
        else:
            if self.V["mode"].get() == "Livestream":
                self._start_live()
            else:
                self._start()

    def _start(self):
        dev = self.V["device"].get()
        if not dev or "no devices" in dev or "Scanning" in dev:
            messagebox.showwarning("No Device","Select a device first!\nEnable USB Debugging.")
            return
        cmd = self._build_cmd()
        self._log(f"\n$ {' '.join(cmd)}")
        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            self.running = True
            self._ui_set_running()
            threading.Thread(target=self._read_output, daemon=True).start()
            threading.Thread(target=self._wait_process,      daemon=True).start()
        except FileNotFoundError:
            messagebox.showerror("Error","scrcpy not found!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _start_live(self):
        dev = self.V["device"].get()
        if not dev or "no devices" in dev or "Scanning" in dev:
            messagebox.showwarning("No Device","Select a device first!")
            return
        key = self.V["live_key"].get().strip()
        if not key:
            messagebox.showwarning("Missing Stream Key","Enter Stream Key first!")
            return
        plat     = self.V["live_platform"].get()
        base     = PLATFORM_RTMP.get(plat,"")
        rtmp_url = key if plat == "Custom" else base + key

        scrcpy_cmd = self._build_cmd(force_always_on_top=True)
        self._log(f"\n$ {' '.join(scrcpy_cmd)}")
        try:
            self.process = subprocess.Popen(
                scrcpy_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.running = True
            self._ui_set_running(label="■   Stop Live", color=RED)
            self._log("→ Waiting for scrcpy window...")
            threading.Thread(
                target=self._wait_process_window_lalu_live,
                args=(rtmp_url, plat), daemon=True).start()
            threading.Thread(target=self._wait_process, daemon=True).start()
        except FileNotFoundError:
            messagebox.showerror("Error","scrcpy not found!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _wait_process_window_lalu_live(self, rtmp_url, plat):
        win_id = None
        for _ in range(20):
            try:
                r = subprocess.run(["xdotool","search","--class","scrcpy"],
                                   capture_output=True, text=True, timeout=2)
                if r.returncode==0 and r.stdout.strip():
                    win_id = r.stdout.strip().splitlines()[0]
                    break
            except FileNotFoundError:
                self._log("ERROR: xdotool not found! sudo apt install xdotool")
                return
            except Exception:
                pass
            time.sleep(0.5)

        if not win_id:
            self._log("ERROR: scrcpy window not found after 10 seconds")
            return

        w = self.winfo_screenwidth()  - (self.winfo_screenwidth()  % 2)
        h = self.winfo_screenheight() - (self.winfo_screenheight() % 2)
        self._log(f"→ Capture fullscreen: {w}x{h}")

        br      = self.V["live_bitrate"].get()
        fps     = self.V["live_fps"].get()
        bufsize = str(int(br.replace("k","")) * 2) + "k"

        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "x11grab", "-draw_mouse", "0",
            "-framerate", fps, "-r", fps,
            "-s", f"{w}x{h}", "-i", ":0.0+0,0",
            "-thread_queue_size", "4096",
            "-f", "pulse", "-ac", "2",
            "-i", "alsa_output.pci-0000_00_1f.3.analog-stereo.monitor",
            *([ "-thread_queue_size","4096","-f","pulse","-ac","2","-i","default",
                "-filter_complex","amix=inputs=2:duration=first:dropout_transition=0"
              ] if self.V["live_mic"].get() else []),
            "-threads", "2",
            "-c:v", "libx264", "-preset", "superfast", "-tune", "zerolatency",
            "-b:v", br, "-maxrate", br, "-bufsize", bufsize,
            "-pix_fmt", "yuv420p", "-g", fps,
            "-af", "aresample=48000:resampler=soxr",
            "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
            "-f", "flv", rtmp_url,
        ]

        self._log(f"$ {' '.join(ffmpeg_cmd)}")
        try:
            self.ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            threading.Thread(target=self._read_ffmpeg_log, daemon=True).start()
            self._log(f"→ Live started to {plat}! 🔴")
            self.tabview.set("📋  Log")
        except Exception as e:
            self._log(f"ERROR ffmpeg: {e}")

    def _read_ffmpeg_log(self):
        if not self.ffmpeg_proc: return
        for baris in self.ffmpeg_proc.stderr:
            baris = baris.decode(errors="replace").rstrip()
            if any(k in baris.lower() for k in ["fps=","bitrate=","error","failed","speed="]):
                self._log(f"[ffmpeg] {baris}")

    def _ui_set_running(self, label="■   Stop", color=RED):
        self.btn_start.configure(text=label, fg_color=color,
                                     hover_color="#cc0000")
        pid  = self.process.pid if self.process else "?"
        mode = self.V["mode"].get()
        st   = f"🔴 LIVE  pid:{pid}" if mode=="Livestream" else f"● {mode}  pid:{pid}"
        self.lbl_status.configure(text=st,
            text_color=RED if mode=="Livestream" else GRN,
            fg_color=CARD2)
        self.lbl_statusbar.configure(text=st)
        self.float_btn_toggle.configure(text="■", text_color=RED)
        if mode == "Livestream":
            self._float_live_mode(True)

    def _read_output(self):
        if self.process:
            for brs in self.process.stdout:
                self._log(brs.rstrip())

    def _wait_process(self):
        if self.process: self.process.wait()
        self.after(0, self._sudah_stop)

    def _stop(self):
        if self.ffmpeg_proc:
            try: self.ffmpeg_proc.terminate()
            except: pass
        if self.process:
            try: self.process.terminate()
            except: pass
        self._sudah_stop()

    def _sudah_stop(self):
        self.running = self.live_running = False
        self.process = self.ffmpeg_proc  = None
        mode  = self.V["mode"].get()
        label = "▶   Start Live" if mode=="Livestream" else "▶   Start"
        self.btn_start.configure(text=label, fg_color=ACC,
                                     hover_color="#0060cc")
        self.lbl_status.configure(text="● Ready", text_color=DIM, fg_color=CARD2)
        self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN")
        self._log("→ stopped\n")
        self.float_btn_toggle.configure(text="▶", text_color=GRN)
        self._float_live_mode(False)

    # ── Misc ──────────────────────────────────────────────────────────────────
    def _pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.V["rec_path"].get())
        if d: self.V["rec_path"].set(d)

    def _save(self):
        self.cfg.update({
            "bitrate":self.V["bitrate"].get(), "max_fps":self.V["fps"].get(),
            "resolution":self.V["resolution"].get(), "codec":self.V["codec"].get(),
            "rotation":self.V["rotation"].get(), "mode":self.V["mode"].get(),
            "record_path":self.V["rec_path"].get(), "record_format":self.V["rec_fmt"].get(),
            "no_audio":self.V["no_audio"].get(), "fullscreen":self.V["fullscreen"].get(),
            "borderless":self.V["borderless"].get(), "always_on_top":self.V["always_top"].get(),
            "stay_awake":self.V["stay_awake"].get(), "turn_screen_off":self.V["screen_off"].get(),
            "no_control":self.V["view_only"].get(), "window_title":self.V["win_title"].get(),
            "live_platform":self.V["live_platform"].get(), "live_key":self.V["live_key"].get(),
            "live_bitrate":self.V["live_bitrate"].get(), "live_resolution":self.V["live_res"].get(),
            "live_fps":self.V["live_fps"].get(), "show_floating":self.V["show_floating"].get(),
            "tcpip_port":self.V["tcpip_port"].get(),
        })
        save_config(self.cfg)
        self.lbl_statusbar.configure(text="✓ Saved")
        self.after(2000, lambda: self.lbl_statusbar.configure(
            text=f"© {datetime.now().year}  VEN"))

    def _copy_cmd(self):
        teks = " ".join(self._build_cmd())
        self.clipboard_clear()
        self.clipboard_append(teks)
        self.lbl_statusbar.configure(text="✓ Copied!")
        self.after(1500, lambda: self.lbl_statusbar.configure(
            text=f"© {datetime.now().year}  VEN"))

    def _reset_config(self):
        if messagebox.askyesno("Reset","Reset all settings to default?"):
            try: os.remove(CONFIG_FILE)
            except: pass
            self.lbl_statusbar.configure(text="Reset — restart for full effect")

    def _on_close(self):
        if self.running or self.live_running:
            if messagebox.askyesno("Quit","Still running. Stop and quit?"):
                self._stop()
                self._destroy_floating()
                self.destroy()
        else:
            self._destroy_floating()
            self.destroy()

    def _destroy_floating(self):
        try:
            if self.float_win and self.float_win.winfo_exists():
                self.float_win.destroy()
        except: pass

    # ── Floating ──────────────────────────────────────────────────────────────
    def _float_live_mode(self, aktif):
        fw = self.float_win
        if aktif:
            fw.attributes("-alpha", 0.0)
            fw.bind("<Enter>", lambda e: fw.attributes("-alpha", 0.92))
            fw.bind("<Leave>", lambda e: fw.attributes("-alpha", 0.0))
        else:
            fw.unbind("<Enter>")
            fw.unbind("<Leave>")
            fw.attributes("-alpha", 1.0)

    def _build_floating(self):
        self.float_win = ctk.CTkToplevel(self)
        fw = self.float_win
        fw.overrideredirect(True)
        fw.attributes("-topmost", True)
        fw.configure(fg_color=CARD)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        # Horizontal layout: drag + divider + play + divider + screenshot
        fw.geometry(f"154x44+{(sw-154)//2}+{sh-60}")

        # Horizontal container
        row = tk.Frame(fw, bg=CARD)
        row.pack(fill="both", expand=True)

        # Drag handle
        drag = tk.Label(row, text="⠿", bg=CARD, fg=BDR,
                        font=(FNM,11), cursor="fleur", padx=6)
        drag.pack(side="left", fill="y")
        drag.bind("<ButtonPress-1>", lambda e: setattr(self,"_dx",e.x) or setattr(self,"_dy",e.y))
        drag.bind("<B1-Motion>",     lambda e: fw.geometry(
            f"+{fw.winfo_x()+e.x-self._dx}+{fw.winfo_y()+e.y-self._dy}"))

        # Divider vertikal
        tk.Frame(row, bg=BDR, width=1).pack(side="left", fill="y", padx=0)

        # Toggle play/stop
        self.float_btn_toggle = ctk.CTkButton(
            row, text="▶", command=self._toggle,
            width=52, height=44, fg_color=CARD, hover_color=CARD2,
            text_color=GRN, font=ctk.CTkFont(FNM,16,"bold"),
            corner_radius=0)
        self.float_btn_toggle.pack(side="left")

        # Divider vertikal
        tk.Frame(row, bg=BDR, width=1).pack(side="left", fill="y")

        # Screenshot
        ctk.CTkButton(row, text="📷", command=self._screenshot,
                      width=52, height=44, fg_color=CARD, hover_color=CARD2,
                      text_color=YEL, font=ctk.CTkFont(FNM,16),
                      corner_radius=0).pack(side="left")

        if not self.V["show_floating"].get():
            fw.withdraw()

    def _screenshot(self):
        dev = self.V["device"].get()
        if not dev or "no devices" in dev or "Scanning" in dev:
            messagebox.showwarning("No Device","Select a device first!")
            return
        serial = dev.split()[0]
        folder = os.path.expanduser("~/Pictures/scrcpy-screenshots")
        os.makedirs(folder, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"ss_{ts}.png")

        def _ambil():
            try:
                hasil = subprocess.run(
                    ["adb","-s",serial,"exec-out","screencap","-p"],
                    capture_output=True, timeout=10)
                if hasil.returncode==0 and hasil.stdout:
                    with open(path,"wb") as f: f.write(hasil.stdout)
                    self._log(f"→ Screenshot saved: {path}")
                    self.after(0, lambda p=path: self._flash_screenshot(p))
                else:
                    self._log("ERROR: Screenshot failed")
            except Exception as e:
                self._log(f"ERROR screenshot: {e}")

        threading.Thread(target=_ambil, daemon=True).start()

    def _flash_screenshot(self, path):
        nama = os.path.basename(path)
        fx = self.float_win.winfo_x()
        fy = self.float_win.winfo_y()
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        toast.configure(fg_color=CARD)
        fr = ctk.CTkFrame(toast, fg_color=CARD, corner_radius=10,
                          border_width=1, border_color=ACC)
        fr.pack(padx=2, pady=2)
        ctk.CTkLabel(fr, text="✓ Screenshot saved",
                     font=ctk.CTkFont(FN,10,"bold"),
                     text_color=GRN, fg_color=CARD,
                     padx=14, pady=8).pack()
        ctk.CTkLabel(fr, text=nama,
                     font=ctk.CTkFont(FN,9),
                     text_color=DIM, fg_color=CARD,
                     padx=14, pady=6).pack()
        toast.update_idletasks()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{fx-max(0,tw-60)}+{fy-th-8}")
        self.after(2500, lambda: toast.destroy() if toast.winfo_exists() else None)


if __name__ == "__main__":
    App().mainloop()
