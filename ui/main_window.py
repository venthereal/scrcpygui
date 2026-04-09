#!/usr/bin/env python3
import customtkinter as ctk  # type: ignore
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Optional
import subprocess, threading, os, json, time, re, math
from datetime import datetime

# ── Core & Config Imports ──────────────────────────────────────────────────
from core.config import CONFIG_FILE, load_config, save_config
from core.adb_manager import (
    PALETTE_DARK, PALETTE_LIGHT, BG, CARD, CARD2, BDR, TEXT, DIM,
    ACC, RED, YEL, GRN, FN, FNM,
    MODES, PLATFORM_RTMP, PRESETS, COMPOSITOR_FIXES,
    detect_audio_monitor, detect_compositor, is_hyprland,
    check_dependencies, check_optional_dependencies,
    scan_devices, enable_tcpip, detect_device_ip, connect_wifi, disconnect_wifi,
    capture_screenshot, capture_device_preview, fetch_device_stats,
)

# ── UI Module Imports ──────────────────────────────────────────────────────
from ui.ui_constants import FS, set_ui_scale
from ui.ui_helpers import detect_system_dpi, apply_palette, configure_ui_scale
from ui.tabs.base_tab import BaseTab
from ui.widgets import PreviewCanvas, FloatingWidget, DeviceBar
from ui.dialogs import DependencyCheckerDialog, HiDPIDialog

# ── PIL / Pillow for preview canvas ────────────────────────────────────────────
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False

PREVIEW_TMP = "/tmp/scrcpygui_preview.png"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.cfg           = load_config()
        self.processes     = {}
        self.running_devs  = set()
        self.dev_rows      = {}
        self.process       = None
        self.ffmpeg_proc   = None
        self.xvfb_proc     = None   # virtual display process for livestream
        self.xvfb_display  = ":99"
        self.running       = False
        self.live_running  = False
        self.key_visible   = False
        self._all_devices  = []
        self._monitor_running = False
        self._prev_net     = None

        # ── Stream preview state ────────────────────────────────────────────────
        self._preview_active     = False
        self._preview_start_time = None
        self._preview_img_ref    = None   # prevent GC on PhotoImage

        # ── Floating window state ───────────────────────────────────────────────
        self._mx = 0  # mouse x for drag tracking
        self._my = 0  # mouse y for drag tracking
        self._dx = 0  # delta x for window position
        self._dy = 0  # delta y for window position

        # ── UI widgets (optional, may be created dynamically) ──────────────────
        self.btn_toggle_cmd: Optional[ctk.CTkButton] = None
        self.frame_cmd_preview: Optional[ctk.CTkFrame] = None

        self.title("ScrcpyGUI")
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.minsize(960, 560)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        W = min(1020, sw - 40)
        H = min(680, sh - 110)
        self.geometry(f"{W}x{H}+{(sw-W)//2}+20")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── Apply saved UI scale before building UI ─────────────────────────
        self._apply_ui_scale(self.cfg.get("ui_scale", 1.0))

        self._setup_vars()
        self._build_ui()
        self._load_config()
        # Splash loading — tampil dulu, defer operasi berat
        self.after(0,    self._show_splash)
        self.after(50,   self._refresh_devices)
        self.after(100,  self._build_floating)
        self.after(300,  self._check_deps_startup)
        self.after(600,  self._check_hidpi_startup)   # HiDPI detection popup
        self.after(800,  self._start_monitor_loop)

    # ── HiDPI / UI Scale ────────────────────────────────────────────────────────────
    def _apply_ui_scale(self, scale: float):
        """Set global UI_SCALE dan resize window sesuai scale."""
        global UI_SCALE
        UI_SCALE = max(0.75, min(2.0, scale))
        # Resize window minimum sesuai scale
        base_w, base_h = 960, 560
        self.minsize(round(base_w * UI_SCALE), round(base_h * UI_SCALE))
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        W = min(round(1020 * UI_SCALE), sw - 40)
        H = min(round(680  * UI_SCALE), sh - 110)
        self.geometry(f"{W}x{H}+{(sw-W)//2}+20")

    def _check_hidpi_startup(self):
        """Cek DPI sistem — kalau HiDPI dan belum pernah ditanya, tampilkan popup."""
        already_asked = self.cfg.get("ui_scale_asked", False)
        if already_asked: return
        def _run():
            dpi = detect_system_dpi()
            if dpi > 120:
                scale = round(dpi / 96.0, 2)
                scale = min(2.0, max(1.0, round(scale * 4) / 4))  # round to 0.25
                self.after(0, lambda: self._show_hidpi_popup(dpi, scale))
        threading.Thread(target=_run, daemon=True).start()

    def _show_hidpi_popup(self, dpi: float, suggested_scale: float):
        """Popup konfirmasi scale untuk HiDPI display."""
        popup = ctk.CTkToplevel(self)
        popup.title("HiDPI Display Detected")
        popup.configure(fg_color=BG)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.grab_set()

        popup.update_idletasks()
        pw, ph = 400, 280
        sx = int(self.winfo_x()) + (int(self.winfo_width())  - pw) // 2
        sy = int(self.winfo_y()) + (int(self.winfo_height()) - ph) // 2
        popup.geometry(f"{pw}x{ph}+{sx}+{sy}")

        # Header
        hdr = ctk.CTkFrame(popup, fg_color=CARD, corner_radius=0, height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="🖥  HiDPI Display Detected",
            font=ctk.CTkFont(FN, FS(13), "bold"), text_color=ACC,
            fg_color="transparent").pack(side="left", padx=16)

        body = ctk.CTkFrame(popup, fg_color=BG)
        body.pack(fill="both", expand=True, padx=20, pady=12)

        ctk.CTkLabel(body,
            text=f"Your display DPI is {dpi:.0f} (normal = 96). UI scale {suggested_scale:.2f}x is recommended.",
            font=ctk.CTkFont(FN, FS(10)), text_color=DIM,
            fg_color="transparent", justify="left", wraplength=340).pack(anchor="w", pady=(0,16))

        # Scale options
        ctk.CTkLabel(body, text="Select UI Scale:",
            font=ctk.CTkFont(FN, FS(9), "bold"), text_color=DIM,
            fg_color="transparent").pack(anchor="w", pady=(0,8))

        scale_var = tk.DoubleVar(value=suggested_scale)
        scale_options = [0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        scale_labels  = ["75%", "100% (default)", "125%", "150%", "175%", "200%"]

        btn_row = ctk.CTkFrame(body, fg_color=BG)
        btn_row.pack(fill="x")
        self._scale_btns = {}
        for val, lbl in zip(scale_options, scale_labels):
            active = abs(val - suggested_scale) < 0.01
            btn = ctk.CTkButton(btn_row, text=lbl,
                width=72, height=28,
                fg_color=ACC if active else CARD,
                hover_color="#0060cc",
                text_color="white" if active else DIM,
                font=ctk.CTkFont(FN, FS(9)),
                border_width=1, border_color=ACC if active else BDR,
                corner_radius=6,
                command=lambda v=val: self._on_scale_btn_select(v, scale_var, scale_options, scale_labels))
            btn.pack(side="left", padx=(0,4))
            self._scale_btns[val] = btn

        # Buttons
        ctk.CTkFrame(body, fg_color=BDR, height=1).pack(fill="x", pady=(16,8))
        act_row = ctk.CTkFrame(body, fg_color=BG)
        act_row.pack(fill="x")

        def _apply():
            scale = scale_var.get()
            self.cfg["ui_scale"] = scale
            self.cfg["ui_scale_asked"] = True
            save_config(self.cfg)
            popup.grab_release(); popup.destroy()
            self._apply_ui_scale(scale)
            self._rebuild_ui()

        def _skip():
            self.cfg["ui_scale_asked"] = True
            save_config(self.cfg)
            popup.grab_release(); popup.destroy()

        ctk.CTkButton(act_row, text="Skip", command=_skip,
            width=80, height=32, fg_color=CARD, hover_color=CARD2,
            text_color=DIM, font=ctk.CTkFont(FN, FS(10)),
            border_width=1, border_color=BDR, corner_radius=8).pack(side="left")

        ctk.CTkButton(act_row, text="✓  Apply Scale", command=_apply,
            width=140, height=32, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN, FS(10), "bold"),
            corner_radius=8).pack(side="right")

    def _on_scale_btn_select(self, val: float, scale_var: tk.DoubleVar,
                              scale_options: list, scale_labels: list):
        """Update tombol scale aktif."""
        scale_var.set(val)
        for v, lbl in zip(scale_options, scale_labels):
            btn = self._scale_btns.get(v)
            if not btn: continue
            active = abs(v - val) < 0.01
            btn.configure(
                fg_color=ACC if active else CARD,
                text_color="white" if active else DIM,
                border_color=ACC if active else BDR)

    # ── Splash ───────────────────────────────────────────────────────────────
    def _show_splash(self):
        """Loading bar splash — muncul di atas window utama, hilang otomatis."""
        splash = ctk.CTkToplevel(self)
        splash.overrideredirect(True)
        splash.attributes("-topmost", True)
        splash.configure(fg_color=CARD)

        SW, SH = 320, 148
        sx = self.winfo_x() + (self.winfo_width()  - SW) // 2
        sy = self.winfo_y() + (self.winfo_height() - SH) // 2
        splash.geometry(f"{SW}x{SH}+{sx}+{sy}")

        # Border frame
        fr = ctk.CTkFrame(splash, fg_color=CARD, corner_radius=12,
                          border_width=1, border_color=BDR)
        fr.pack(fill="both", expand=True, padx=2, pady=2)

        # App name
        ctk.CTkLabel(fr, text="ScrcpyGUI",
            font=ctk.CTkFont(FN,FS(16), "bold"), text_color=TEXT,
            fg_color="transparent").pack(pady=(18, 2))
        ctk.CTkLabel(fr, text="Starting up…",
            font=ctk.CTkFont(FN,FS(9)), text_color=DIM,
            fg_color="transparent").pack()

        # Progress bar
        bar = ctk.CTkProgressBar(fr, width=240, height=6,
            fg_color=CARD2, progress_color=ACC, corner_radius=4)
        bar.set(0)
        bar.pack(pady=(14, 4))

        # Step label
        lbl_step = ctk.CTkLabel(fr, text="Initializing…",
            font=ctk.CTkFont(FN,FS(8)), text_color=DIM, fg_color="transparent")
        lbl_step.pack()

        # Steps sesuai defer timing
        steps = [
            (50,  0.25, "Scanning devices…"),
            (100, 0.50, "Building widgets…"),
            (300, 0.75, "Checking dependencies…"),
            (800, 1.00, "Ready!"),
        ]

        def _step(idx):
            if idx >= len(steps): return
            delay, progress, label = steps[idx]
            bar.set(progress)
            lbl_step.configure(text=label)
            if idx < len(steps) - 1:
                splash.after(steps[idx+1][0] - delay, lambda: _step(idx + 1))
            else:
                # Selesai — tutup splash
                splash.after(300, lambda: splash.destroy() if splash.winfo_exists() else None)

        splash.after(50, lambda: _step(0))

    # ── Vars ──────────────────────────────────────────────────────────────────
    def _setup_vars(self):
        self.V = {
            "device":        tk.StringVar(),
            "bitrate":       tk.StringVar(value="8M"),
            "fps":           tk.StringVar(value="60"),
            "resolution":    tk.StringVar(value="(default)"),
            "codec":         tk.StringVar(value="h264"),
            "video_encoder":  tk.StringVar(value="(auto)"),
            "rotation":      tk.StringVar(value="0"),
            "mode":          tk.StringVar(value="Mirror Only"),
            "rec_path":      tk.StringVar(value=os.path.expanduser("~/Videos/scrcpy")),
            "rec_fmt":       tk.StringVar(value="mp4"),
            "no_audio":      tk.BooleanVar(value=False),
            "audio_output":  tk.BooleanVar(value=False),
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
            "live_custom_url": tk.StringVar(value=""),
            "show_floating": tk.BooleanVar(value=True),
            "tcpip_port":    tk.StringVar(value="5555"),
            "tcpip_host":    tk.StringVar(value=""),
            "theme":         tk.StringVar(value="dark"),
            "show_monitor":        tk.BooleanVar(value=True),
            "cmd_preview_visible": tk.BooleanVar(value=False),
            "log_visible":         tk.BooleanVar(value=True),
            "minimize_to_tray":    tk.BooleanVar(value=False),
            # 
            "preview_interval":   tk.StringVar(value="2s"),
            "preview_auto_start": tk.BooleanVar(value=True),
        }
        for v in self.V.values():
            v.trace_add("write", lambda *_: self.after(20, self._preview))
        self.V["live_platform"].trace_add("write", lambda *_: self.after(20, self._update_rtmp_hint))
        self.V["mode"].trace_add("write",          lambda *_: self.after(20, self._update_mode_ui))
        self.V["show_floating"].trace_add("write",  lambda *_: self.after(20, self._toggle_floating_visibility))
        self.V["show_monitor"].trace_add("write",   lambda *_: self.after(20, self._toggle_monitor_visibility))
        self.V["log_visible"].trace_add("write",    lambda *_: self.after(20, self._toggle_log_panel))

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
            text_color=DIM, border_color=BDR, border_width=1)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(8,8))
        for tab in ["📱  Mirror","🔴  Livestream","📶  TCP/IP","⚙️  Settings","📋  Log"]:
            self.tabview.add(tab)
            self.tabview.tab(tab).configure(fg_color=BG)
        self._build_tab_mirror()
        self._build_tab_live()
        self._build_tab_tcpip()
        self._build_tab_settings()
        self._build_tab_log()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0, height=52)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="ScrcpyGUI", font=ctk.CTkFont(FN,FS(14),"bold"),
                     text_color=TEXT, fg_color=CARD).pack(side="left", padx=16)
        ctk.CTkLabel(hdr, text="Beta", font=ctk.CTkFont(FN,FS(11)),
                     text_color=DIM, fg_color=CARD).pack(side="left")
        self.lbl_status = ctk.CTkLabel(hdr, text="● Ready",
            font=ctk.CTkFont(FNM,FS(10),"bold"), text_color=DIM,
            fg_color=CARD2, corner_radius=8, padx=12, pady=4)
        self.lbl_status.pack(side="right", padx=16, pady=10)
        # Compositor / display server badge — always visible
        _comp = detect_compositor()
        if _comp and _comp in COMPOSITOR_FIXES:
            _badge_label = COMPOSITOR_FIXES[_comp][2]
            _badge_color = COMPOSITOR_FIXES[_comp][3]
        elif os.environ.get("WAYLAND_DISPLAY"):
            _badge_label = " Wayland"
            _badge_color = "#cba6f7"
        else:
            _badge_label = " X11"
            _badge_color = "#a6e3a1"
        ctk.CTkLabel(hdr, text=_badge_label,
            font=ctk.CTkFont(FN,FS(8),"bold"), text_color=_badge_color,
            fg_color=CARD2, corner_radius=6, padx=8, pady=4
        ).pack(side="right", padx=(0,6), pady=10)
        ctk.CTkFrame(self, fg_color=BDR, height=1, corner_radius=0).pack(fill="x")

    # ── Device bar ────────────────────────────────────────────────────────────
    def _build_devicebar(self):
        bar = ctk.CTkFrame(self, fg_color=BG)
        bar.pack(fill="x", padx=16, pady=(12,4))
        ctk.CTkLabel(bar, text="DEVICE", font=ctk.CTkFont(FN,FS(9),"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left", padx=(0,8))
        self.combo_device = ctk.CTkComboBox(
            bar, values=[], variable=self.V["device"], width=320,
            font=ctk.CTkFont(FNM,FS(10)), fg_color=CARD, border_color=BDR,
            button_color=ACC, dropdown_fg_color=CARD, dropdown_text_color=TEXT,
            text_color=TEXT, state="readonly",
            command=lambda val: self._on_device_selected(val))
        self.combo_device.pack(side="left", padx=(0,8))
        ctk.CTkButton(bar, text="↺  Refresh", command=self._refresh_devices,
                      width=110, height=32, fg_color=CARD, hover_color=CARD2,
                      text_color=ACC, font=ctk.CTkFont(FN,FS(10),"bold"),
                      border_width=1, border_color=BDR, corner_radius=8
                      ).pack(side="left", padx=(0,8))
        self.lbl_device_info = ctk.CTkLabel(bar, text="", font=ctk.CTkFont(FN,FS(9)),
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
            ("Bit rate",       ["1M","2M","4M","6M","8M","10M","12M","16M","20M","25M"],"bitrate","Mbps"),
            ("Max FPS",        ["15","24","30","45","60","90","120"],                    "fps","fps"),
            ("Max resolution", ["(default)","480","720","1080","1280","1440","1920"],    "resolution","px"),
            ("Codec",          ["h264","h265","av1"],                                    "codec",""),
            ("Rotation",       ["0","90","180","270"],                                   "rotation","°"),
        ]:
            row = ctk.CTkFrame(left, fg_color=BG); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=150, anchor="w",
                         font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
            self._combo_ctk(row, vals, self.V[key], 120).pack(side="left", padx=(0,6))
            if unit:
                ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(FN,FS(9)),
                             text_color=DIM, fg_color=BG).pack(side="left")

        # Video Encoder row — populated dynamically when a device is selected
        row_enc = ctk.CTkFrame(left, fg_color=BG); row_enc.pack(fill="x", pady=4)
        ctk.CTkLabel(row_enc, text="Video Encoder", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        self.combo_encoder = self._combo_ctk(row_enc, ["(auto)"], self.V["video_encoder"], 220)
        self.combo_encoder.pack(side="left", padx=(0,6))
        self.lbl_encoder_hint = ctk.CTkLabel(row_enc, text="",
            font=ctk.CTkFont(FN,FS(8)), text_color=DIM, fg_color=BG)
        self.lbl_encoder_hint.pack(side="left")

        self._section(left, "OUTPUT MODE")
        mode_cards = ctk.CTkFrame(left, fg_color=BG)
        mode_cards.pack(fill="x", pady=(6,0))
        self._mode_btns = {}
        for m, icon, label in [("Mirror Only","📱","Mirroring"),("Record","⏺","Record")]:
            active = self.V["mode"].get() == m
            card = ctk.CTkFrame(mode_cards, fg_color=ACC if active else CARD,
                                corner_radius=12, border_width=2,
                                border_color=ACC if active else BDR, width=88, height=68)
            card.pack(side="left", padx=(0,8)); card.pack_propagate(False)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(FN,FS(20)), fg_color="transparent",
                         text_color="white" if active else DIM).pack(pady=(10,0))
            ctk.CTkLabel(card, text=label, font=ctk.CTkFont(FN,FS(9),"bold"), fg_color="transparent",
                         text_color="white" if active else TEXT).pack()
            for w in [card]+card.winfo_children():
                w.bind("<Button-1>", lambda e, v=m: self._set_mode(v))
                w.configure(cursor="hand2")
            self._mode_btns[m] = card

        self.frame_mode = ctk.CTkFrame(left, fg_color=BG)
        self.frame_mode.pack(fill="x", pady=(10,0))

        self._section(right, "DISPLAY OPTIONS")
        options = [("No audio","no_audio"),("Audio on device","audio_output"),("Fullscreen","fullscreen"),("Borderless","borderless"),
                   ("Always on top","always_top"),("Stay awake","stay_awake"),
                   ("Turn screen off","screen_off"),("View only","view_only")]
        grid = ctk.CTkFrame(right, fg_color=BG); grid.pack(fill="x", pady=4)
        for i, (teks, key) in enumerate(options):
            ctk.CTkCheckBox(grid, text=teks, variable=self.V[key],
                font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=ACC,
                hover_color="#0060cc", checkmark_color=TEXT, border_color=BDR,
                width=20, height=20, command=lambda: self.after(20, self._preview)
            ).grid(row=i//2, column=i%2, sticky="w", padx=(0,20), pady=5)

        self._section(right, "WINDOW")
        row = ctk.CTkFrame(right, fg_color=BG); row.pack(fill="x", pady=3)
        ctk.CTkLabel(row, text="Window title", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.V["win_title"], width=180,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,FS(10))).pack(side="left")

        ctk.CTkFrame(right, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", pady=(16,0))
        # dummy hidden widget so _preview() does not error
        self.txt_cmd = ctk.CTkTextbox(right, height=1, fg_color=BG, border_width=0)
        self.txt_cmd.pack_forget()
        self.txt_cmd.configure(state="disabled")
        btn_row = ctk.CTkFrame(right, fg_color=BG)
        btn_row.pack(fill="x", pady=(8,4))
        self.btn_start = ctk.CTkButton(btn_row, text="▶  Start", command=self._toggle,
            height=38, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN,FS(11),"bold"), corner_radius=8)
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0,6))
        self.btn_start_all = ctk.CTkButton(btn_row, text="▶▶  All", command=self._start_all,
            height=38, fg_color=GRN, hover_color="#28a745", state="disabled",
            text_color="white", font=ctk.CTkFont(FN,FS(11),"bold"), corner_radius=8)
        self.btn_start_all.pack(side="left", fill="x", expand=True)
        self.lbl_statusbar = ctk.CTkLabel(right, text=f"© {datetime.now().year}  VEN",
            font=ctk.CTkFont(FN,FS(9)), text_color=DIM, fg_color=BG)
        self.lbl_statusbar.pack(anchor="center", pady=(0,4))

    # ── Tab Live (preview canvas on right panel) ───────────────────────────────
    def _build_tab_live(self):
        tab = self.tabview.tab("🔴  Livestream")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        # ── Left: Stream config (unchanged) ──────────────────────────────────
        self._section(left, "PLATFORM & STREAM KEY")
        row = ctk.CTkFrame(left, fg_color=BG); row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Platform", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        self._combo_ctk(row, list(PLATFORM_RTMP.keys()), self.V["live_platform"], 140).pack(side="left")

        self.lbl_stream_key_label = ctk.CTkLabel(left, text="Stream Key",
            font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG)
        self.lbl_stream_key_label.pack(anchor="w", pady=(10,2))

        self.frame_custom_url = ctk.CTkFrame(left, fg_color=BG)
        self.frame_custom_url.pack(fill="x", pady=(0,4))
        ctk.CTkLabel(self.frame_custom_url, text="RTMP URL",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(anchor="w", pady=(0,2))
        ctk.CTkEntry(self.frame_custom_url, textvariable=self.V["live_custom_url"],
                     placeholder_text="rtmp://your-server.com/live/",
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,FS(10))).pack(fill="x")
        self.frame_custom_url.pack_forget()

        self.entry_stream_key = ctk.CTkEntry(left, textvariable=self.V["live_key"],
            show="•", fg_color=CARD, border_color=BDR, text_color=TEXT, font=ctk.CTkFont(FNM,FS(10)))
        self.entry_stream_key.pack(fill="x", pady=(0,4))

        self.btn_toggle_key = ctk.CTkButton(left, text="👁  Show Key",
            command=self._toggle_key_visibility, width=120, height=28,
            fg_color=CARD2, hover_color=BDR, text_color=DIM,
            font=ctk.CTkFont(FN,FS(9)), corner_radius=6, border_width=1, border_color=BDR)
        self.btn_toggle_key.pack(anchor="w", pady=(0,4))

        self.lbl_rtmp = ctk.CTkLabel(left, text="", font=ctk.CTkFont(FN,FS(8)),
            text_color=DIM, fg_color=BG, wraplength=340, justify="left")
        self.lbl_rtmp.pack(anchor="w", pady=(2,0))

        self._section(left, "STREAM QUALITY")
        for label, vals, key, unit in [
            ("Video bitrate",["1000k","1500k","2000k","2500k","3000k","4000k","5000k","6000k"],"live_bitrate","bps"),
            ("Resolution",   ["854x480","1280x720","1920x1080"],                               "live_res",""),
            ("Stream FPS",   ["24","25","30","48","60"],                                        "live_fps","fps"),
        ]:
            row = ctk.CTkFrame(left, fg_color=BG); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=150, anchor="w",
                         font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
            self._combo_ctk(row, vals, self.V[key], 130).pack(side="left", padx=(0,6))
            if unit:
                ctk.CTkLabel(row, text=unit, font=ctk.CTkFont(FN,FS(9)),
                             text_color=DIM, fg_color=BG).pack(side="left")

        ctk.CTkCheckBox(left, text="🎙  Enable Microphone", variable=self.V["live_mic"],
            font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=ACC, hover_color="#0060cc",
            checkmark_color=TEXT, border_color=BDR, width=20, height=20,
            command=lambda: self.after(20, self._preview)).pack(anchor="w", pady=(12,0))

        # ── Start Livestream Button ────────────────────────────────────────────────
        ctk.CTkFrame(left, fg_color=BG, height=20).pack()
        self.btn_start_live = ctk.CTkButton(left, text="🔴  Start Livestream", command=lambda: (self.V["mode"].set("Livestream"), self._toggle()),
            height=38, fg_color=RED, hover_color="#cc0000",
            text_color="white", font=ctk.CTkFont(FN,FS(11),"bold"), corner_radius=8)
        self.btn_start_live.pack(fill="x")

        # ── Right panel — Stream Preview Canvas ──────────────────────────────
        self._section(right, "STREAM PREVIEW")

        # PIL warning badge
        if not PIL_OK:
            warn = ctk.CTkFrame(right, fg_color=CARD2, corner_radius=6,
                                border_width=1, border_color=YEL)
            warn.pack(fill="x", pady=(0,6))
            ctk.CTkLabel(warn, text="⚠  Pillow is optional",
                         font=ctk.CTkFont(FN,FS(9),"bold"), text_color=YEL,
                         fg_color="transparent", padx=10, pady=4).pack(side="left")
            ctk.CTkLabel(warn, text="Preview may still work using Tk PNG support",
                         font=ctk.CTkFont(FNM,FS(9)), text_color=DIM,
                         fg_color="transparent", padx=6).pack(side="left")

        # Canvas container (16:9 aspect)
        PREV_W, PREV_H = 316, 178
        self.preview_outer = ctk.CTkFrame(right, fg_color=CARD, corner_radius=8,
                                          border_width=1, border_color=BDR)
        self.preview_outer.pack(pady=(2,0))

        self.preview_canvas = tk.Canvas(
            self.preview_outer, width=PREV_W, height=PREV_H,
            bg="#111111", highlightthickness=0, cursor="crosshair")
        self.preview_canvas.pack(padx=2, pady=2)
        self._preview_placeholder()

        # Gap antara canvas dan stats bar
        ctk.CTkFrame(right, fg_color=BG, height=4).pack(fill="x")

        # Stats overlay bar below canvas
        stats_bar = ctk.CTkFrame(right, fg_color=CARD2, corner_radius=6,
                                 border_width=1, border_color=BDR, height=26)
        stats_bar.pack(fill="x"); stats_bar.pack_propagate(False)

        self.lbl_preview_time = ctk.CTkLabel(stats_bar, text="--:--:--",
            font=ctk.CTkFont(FNM,FS(9),"bold"), text_color=DIM, fg_color="transparent")
        self.lbl_preview_time.pack(side="left", padx=8)

        self.lbl_preview_status = ctk.CTkLabel(stats_bar, text="idle",
            font=ctk.CTkFont(FN,FS(8)), text_color=DIM, fg_color="transparent")
        self.lbl_preview_status.pack(side="left")

        self.lbl_preview_res = ctk.CTkLabel(stats_bar, text="",
            font=ctk.CTkFont(FNM,FS(8)), text_color=DIM, fg_color="transparent")
        self.lbl_preview_res.pack(side="right", padx=8)

        # Preview controls
        ctrl = ctk.CTkFrame(right, fg_color=BG); ctrl.pack(fill="x", pady=(6,0))

        self.btn_preview_toggle = ctk.CTkButton(
            ctrl, text="📷  Capture", command=self._toggle_preview,
            width=110, height=28, fg_color=CARD2, hover_color=BDR,
            text_color=DIM, font=ctk.CTkFont(FN,FS(9),"bold"),
            border_width=1, border_color=BDR, corner_radius=8)
        self.btn_preview_toggle.pack(side="left", padx=(0,8))

        ctk.CTkLabel(ctrl, text="Interval", font=ctk.CTkFont(FN,FS(9)),
                     text_color=DIM, fg_color=BG).pack(side="left", padx=(0,4))
        self._combo_ctk(ctrl, ["1s","2s","3s","5s"],
                        self.V["preview_interval"], 68).pack(side="left", padx=(0,10))

        ctk.CTkCheckBox(ctrl, text="Auto", variable=self.V["preview_auto_start"],
            font=ctk.CTkFont(FN,FS(9)), text_color=DIM, fg_color=ACC,
            hover_color="#0060cc", checkmark_color=TEXT, border_color=BDR,
            width=16, height=16).pack(side="left")

        # dummy hidden widget so _preview() does not error
        self.txt_cmd_live = ctk.CTkTextbox(right, height=1, fg_color=BG, border_width=0)
        self.txt_cmd_live.pack_forget()
        self.txt_cmd_live.configure(state="disabled")

    # ── Tab TCP/IP ────────────────────────────────────────────────────────────
    def _build_tab_tcpip(self):
        tab = self.tabview.tab("📶  TCP/IP")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        self._section(left, "CONNECT VIA WIFI")
        info_frame = ctk.CTkFrame(left, fg_color=CARD2, corner_radius=8,
                                  border_width=1, border_color=BDR)
        info_frame.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(info_frame,
            text="Connect phone via USB first, then enable TCP/IP.\nAfter that you can disconnect USB and use WiFi.",
            font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=CARD2,
            justify="left", wraplength=340,
            padx=12, pady=10).pack(fill="x", padx=8, pady=4)

        row = ctk.CTkFrame(left, fg_color=BG); row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text="Port", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkEntry(row, textvariable=self.V["tcpip_port"], width=100,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,FS(10))).pack(side="left")
        ctk.CTkLabel(row, text="(default: 5555)", font=ctk.CTkFont(FN,FS(9)),
                     text_color=DIM, fg_color=BG).pack(side="left", padx=8)

        ctk.CTkButton(left, text="Step 1: Enable TCP/IP (USB required)",
            command=self._enable_tcpip, height=38, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN,FS(11),"bold"), corner_radius=8
            ).pack(fill="x", pady=(8,4))

        row2 = ctk.CTkFrame(left, fg_color=BG); row2.pack(fill="x", pady=(12,4))
        ctk.CTkLabel(row2, text="Device IP", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkEntry(row2, textvariable=self.V["tcpip_host"], width=150,
                     placeholder_text="e.g. 192.168.1.100",
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,FS(10))).pack(side="left", padx=(0,6))
        ctk.CTkButton(row2, text="🔍 Auto", command=self._auto_detect_ip,
                      width=80, height=30, fg_color=CARD2, hover_color=BDR,
                      text_color=DIM, font=ctk.CTkFont(FN,FS(9),"bold"),
                      border_width=1, border_color=BDR, corner_radius=8).pack(side="left")

        ctk.CTkButton(left, text="Step 2: Connect via WiFi", command=self._connect_wifi,
            height=38, fg_color=GRN, hover_color="#28a745",
            text_color="white", font=ctk.CTkFont(FN,FS(11),"bold"), corner_radius=8
            ).pack(fill="x", pady=4)

        self._section(left, "BACK TO USB")
        ctk.CTkButton(left, text="Disconnect WiFi & Switch to USB",
            command=self._disconnect_wifi, height=38, fg_color=CARD2, hover_color=BDR,
            text_color=TEXT, font=ctk.CTkFont(FN,FS(11)),
            border_width=1, border_color=BDR, corner_radius=8).pack(fill="x", pady=4)

        self._section(right, "TCP/IP LOG")
        self.txt_tcpip = ctk.CTkTextbox(right, height=300, fg_color=CARD, text_color=TEXT,
            font=ctk.CTkFont(FNM,FS(9)), border_color=BDR, border_width=1, wrap="word")
        self.txt_tcpip.pack(fill="both", expand=True)
        self.txt_tcpip.configure(state="disabled")
        self.txt_tcpip._textbox.tag_configure("ok",    foreground=GRN)
        self.txt_tcpip._textbox.tag_configure("error", foreground=RED)
        self.txt_tcpip._textbox.tag_configure("info",  foreground=ACC)

    # ── Tab Settings ──────────────────────────────────────────────────────────
    def _build_tab_settings(self):
        tab = self.tabview.tab("⚙️  Settings")
        left  = ctk.CTkFrame(tab, fg_color=BG)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))
        right = ctk.CTkFrame(tab, fg_color=BG)
        right.pack(side="left", fill="both", expand=True)

        self._section(left, "TOOLS")
        toggles = [
            ("Floating Widget", "show_floating"),
            ("Device Monitor",  "show_monitor"),
            ("Log Panel",       "log_visible"),
        ]
        for label, key in toggles:
            row = ctk.CTkFrame(left, fg_color=BG); row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=150, anchor="w",
                         font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=BG).pack(side="left")
            ctk.CTkSwitch(row, text="Show", variable=self.V[key],
                font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BDR,
                progress_color=ACC, button_color=CARD, button_hover_color=CARD2).pack(side="left")

        row_t = ctk.CTkFrame(left, fg_color=BG); row_t.pack(fill="x", pady=4)
        ctk.CTkLabel(row_t, text="Minimize to Tray", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=BG).pack(side="left")
        ctk.CTkSwitch(row_t, text="On close", variable=self.V["minimize_to_tray"],
            font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BDR,
            progress_color=ACC, button_color=CARD, button_hover_color=CARD2).pack(side="left")

        # UI Scale row
        row_sc = ctk.CTkFrame(left, fg_color=BG); row_sc.pack(fill="x", pady=4)
        ctk.CTkLabel(row_sc, text="UI Scale", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=BG).pack(side="left")
        cur_scale = self.cfg.get("ui_scale", 1.0)
        self.lbl_cur_scale = ctk.CTkLabel(row_sc,
            text=f"{cur_scale:.0%}", width=48, anchor="w",
            font=ctk.CTkFont(FNM,FS(10),"bold"), text_color=ACC, fg_color="transparent")
        self.lbl_cur_scale.pack(side="left", padx=(0,8))
        ctk.CTkButton(row_sc, text="↺ Re-detect",
            command=self._rescale_ui,
            width=100, height=26, fg_color=CARD2, hover_color=BDR,
            text_color=DIM, font=ctk.CTkFont(FN,FS(9)),
            border_width=1, border_color=BDR, corner_radius=6).pack(side="left")

        row_th = ctk.CTkFrame(left, fg_color=BG); row_th.pack(fill="x", pady=4)
        ctk.CTkLabel(row_th, text="Theme", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=TEXT, fg_color=BG).pack(side="left")
        self.btn_theme_dark = ctk.CTkButton(
            row_th, text="🌙 Dark", command=lambda: self._switch_theme("dark"),
            width=80, height=28, fg_color=ACC if self.V["theme"].get()=="dark" else CARD,
            hover_color="#0060cc", text_color="white",
            font=ctk.CTkFont(FN,FS(10),"bold"), border_width=1, border_color=BDR, corner_radius=8)
        self.btn_theme_dark.pack(side="left", padx=(0,6))
        self.btn_theme_light = ctk.CTkButton(
            row_th, text="☀️ Light", command=lambda: self._switch_theme("light"),
            width=80, height=28, fg_color=ACC if self.V["theme"].get()=="light" else CARD,
            hover_color="#0060cc", text_color="white" if self.V["theme"].get()=="light" else DIM,
            font=ctk.CTkFont(FN,FS(10),"bold"), border_width=1, border_color=BDR, corner_radius=8)
        self.btn_theme_light.pack(side="left")

        self._section(left, "QUICK PRESET")
        preset_frame = ctk.CTkFrame(left, fg_color=BG)
        preset_frame.pack(fill="x", pady=(6,0))
        self._preset_cards = {}
        preset_defs = [
            ("Performance", "🎮", ACC),
            ("Balanced",    "⚡", "#ff9f0a"),
            ("Saver",       "🍃", GRN),
        ]
        for pname, icon, color in preset_defs:
            card = ctk.CTkFrame(preset_frame, fg_color=CARD, corner_radius=12,
                                border_width=2, border_color=BDR, width=88, height=68)
            card.pack(side="left", padx=(0,8)); card.pack_propagate(False)
            ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(FN,FS(20)),
                         fg_color="transparent", text_color=color).pack(pady=(10,0))
            ctk.CTkLabel(card, text=pname, font=ctk.CTkFont(FN,FS(9),"bold"),
                         fg_color="transparent", text_color=TEXT).pack()
            for w in [card]+card.winfo_children():
                w.bind("<Button-1>", lambda e, n=pname: self._apply_preset(n))
                w.configure(cursor="hand2")
            self._preset_cards[pname] = (card, color)

        self._section(left, "PRESET")
        btn_row = ctk.CTkFrame(left, fg_color=BG)
        btn_row.pack(fill="x", pady=(4,0))
        for txt, cmd in [("💾 Save",self._save),("📋 Copy",self._copy_cmd),("🔄 Reset",self._reset_config)]:
            ctk.CTkButton(btn_row, text=txt, command=cmd, height=32,
                fg_color=CARD, hover_color=CARD2, text_color=TEXT,
                font=ctk.CTkFont(FN,FS(9)), border_width=1, border_color=BDR,
                corner_radius=8).pack(side="left", padx=(0,6))

        self._section(right, "ABOUT")
        af = ctk.CTkFrame(right, fg_color=CARD, corner_radius=10,
                          border_width=1, border_color=BDR)
        af.pack(fill="x", pady=4)

        ctk.CTkLabel(af, text="ScrcpyGUI", font=ctk.CTkFont(FN,FS(15),"bold"),
                     text_color=TEXT, fg_color=CARD).pack(anchor="w", padx=14, pady=(10,0))
        ctk.CTkLabel(af, text="Beta  ·  Built for Android Casting",
                     font=ctk.CTkFont(FN,FS(9)), text_color=DIM, fg_color=CARD).pack(anchor="w", padx=14, pady=(2,8))
        ctk.CTkFrame(af, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", padx=12)

        # Dep section — ringkas, detail di popup
        dep_hdr = ctk.CTkFrame(af, fg_color=CARD)
        dep_hdr.pack(fill="x", padx=12, pady=(8,8))
        ctk.CTkLabel(dep_hdr, text="DEPENDENCIES", font=ctk.CTkFont(FN,FS(8),"bold"),
                     text_color=DIM, fg_color=CARD).pack(side="left")
        self.btn_recheck_deps = ctk.CTkButton(
            dep_hdr, text="↺ Check All",
            command=self._show_deps_popup,
            width=90, height=24, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN,FS(8),"bold"),
            corner_radius=6)
        self.btn_recheck_deps.pack(side="right")
        # Summary dot row — ringkas
        self._dep_summary_lbl = ctk.CTkLabel(af, text="Click ↺ Check All to verify",
            font=ctk.CTkFont(FN,FS(8)), text_color=DIM, fg_color=CARD,
            anchor="w")
        self._dep_summary_lbl.pack(anchor="w", padx=14, pady=(0,8))
        self._dep_rows = {}  # kept for compatibility with _update_dep_ui

        ctk.CTkFrame(af, fg_color=BDR, height=1, corner_radius=0).pack(fill="x", padx=12, pady=(8,0))
        ctk.CTkLabel(af, text=f"© {datetime.now().year}  VEN  —  All rights reserved",
                     font=ctk.CTkFont(FN,FS(8)), text_color=DIM, fg_color=CARD).pack(anchor="w", padx=14, pady=(4,8))

        self.tabview.configure(command=self._on_tab_change)

    # ── Tab Log ───────────────────────────────────────────────────────────────
    def _build_tab_log(self):
        tab = self.tabview.tab("📋  Log")
        bar = ctk.CTkFrame(tab, fg_color=BG); bar.pack(fill="x", pady=(0,8))
        ctk.CTkLabel(bar, text="ADB & FFMPEG LOG", font=ctk.CTkFont(FN,FS(9),"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkButton(bar, text="🗑  Clear", command=self._clear_log,
                      width=80, height=28, fg_color=CARD2, hover_color=BDR,
                      text_color=DIM, font=ctk.CTkFont(FN,FS(9)),
                      border_width=1, border_color=BDR, corner_radius=6).pack(side="right")
        self.frame_log_panel = ctk.CTkFrame(tab, fg_color=BG)
        self.txt_log = ctk.CTkTextbox(self.frame_log_panel, fg_color=CARD,
            text_color="#555555", font=ctk.CTkFont(FNM,FS(9)),
            border_color=BDR, border_width=1, wrap="word")
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.configure(state="disabled")
        self.txt_log._textbox.tag_configure("error", foreground=RED)
        self.txt_log._textbox.tag_configure("ok",    foreground=GRN)
        self.txt_log._textbox.tag_configure("cmd",   foreground=YEL)
        self.txt_log._textbox.tag_configure("redup", foreground="#aaaaaa")
        if self.V["log_visible"].get():
            self.frame_log_panel.pack(fill="both", expand=True)

    def _clear_log(self):
        self.txt_log.configure(state="normal")
        self.txt_log.delete("0.0","end")
        self.txt_log.configure(state="disabled")

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _section(self, parent, title):
        f = ctk.CTkFrame(parent, fg_color=BG); f.pack(fill="x", pady=(12,6))
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(FN,FS(8),"bold"),
                     text_color=DIM, fg_color=BG).pack(side="left")
        ctk.CTkFrame(f, fg_color=BDR, height=1, corner_radius=0).pack(
            side="left", fill="x", expand=True, padx=(8,0), pady=6)

    def _combo_ctk(self, parent, values, var, width=120):
        return ctk.CTkComboBox(parent, values=values, variable=var, width=width,
            font=ctk.CTkFont(FNM,FS(10)), fg_color=CARD, border_color=BDR,
            button_color=CARD2, button_hover_color=BDR, dropdown_fg_color=CARD,
            dropdown_text_color=TEXT, text_color=TEXT, state="readonly",
            command=lambda _: self.after(20, self._preview))

    def _toggle_key_visibility(self):
        self.key_visible = not self.key_visible
        self.entry_stream_key.configure(show="" if self.key_visible else "•")
        self.btn_toggle_key.configure(text="🔒 Hide Key" if self.key_visible else "👁  Show Key")

    def _toggle_floating_visibility(self):
        if not hasattr(self, "float_win"): return
        self.float_win.deiconify() if self.V["show_floating"].get() else self.float_win.withdraw()

    def _toggle_monitor_visibility(self):
        if not hasattr(self, "monitor_win"): return
        if self.V["show_monitor"].get():
            self.monitor_win.deiconify(); self._monitor_running = True
        else:
            self.monitor_win.withdraw(); self._monitor_running = False

    def _toggle_log_panel(self):
        if not hasattr(self, "frame_log_panel"): return
        if self.V["log_visible"].get():
            self.frame_log_panel.pack(fill="both", expand=True)
        else:
            self.frame_log_panel.pack_forget()

    def _toggle_cmd_preview(self):
        visible = not self.V["cmd_preview_visible"].get()
        self.V["cmd_preview_visible"].set(visible)
        if self.btn_toggle_cmd:
            self.btn_toggle_cmd.configure(text="▼" if visible else "▶")
        if self.frame_cmd_preview:
            if visible: self.frame_cmd_preview.pack(fill="x", pady=(4,0))
            else:       self.frame_cmd_preview.pack_forget()

    def _update_rtmp_hint(self):
        if not hasattr(self,"lbl_rtmp"): return
        plat = self.V["live_platform"].get()
        base = PLATFORM_RTMP.get(plat,"")
        if plat == "Custom":
            self.frame_custom_url.pack(fill="x", pady=(0,4), before=self.lbl_stream_key_label)
            self.lbl_rtmp.pack(anchor="w", pady=(2,0))
            self.lbl_rtmp.configure(text="Final URL = RTMP URL + Stream Key")
        else:
            self.frame_custom_url.pack_forget()
            self.lbl_rtmp.pack_forget()

    def _set_mode(self, mode: str):
        self.V["mode"].set(mode)
        # Only update buttons that exist in this tab's _mode_btns
        for m, card in self._mode_btns.items():
            active = m == mode
            card.configure(fg_color=ACC if active else CARD, border_color=ACC if active else BDR)
            colors = ["white","white"] if active else [DIM,TEXT]
            for i, w in enumerate(card.winfo_children()[:2]):
                try: w.configure(text_color=colors[i])
                except: pass

    def _update_mode_ui(self):
        for w in self.frame_mode.winfo_children(): w.destroy()
        mode = self.V["mode"].get()
        if mode == "Record": self._ui_record(self.frame_mode)
        if not self.running:
            self.btn_start.configure(text="▶   Start Live" if mode=="Livestream" else "▶   Start")
        self.after(20, self._preview)

    def _ui_record(self, p):
        ctk.CTkLabel(p, text="Save folder", font=ctk.CTkFont(FN,FS(10)),
                     text_color=DIM, fg_color=BG).pack(anchor="w", pady=(8,2))
        row = ctk.CTkFrame(p, fg_color=BG); row.pack(fill="x", pady=(0,4))
        ctk.CTkEntry(row, textvariable=self.V["rec_path"], width=240,
                     fg_color=CARD, border_color=BDR, text_color=TEXT,
                     font=ctk.CTkFont(FNM,FS(10))).pack(side="left", padx=(0,6))
        ctk.CTkButton(row, text="…", command=self._pick_folder, width=36, height=32,
                      fg_color=CARD2, hover_color=BDR, text_color=ACC,
                      font=ctk.CTkFont(FN,FS(12),"bold"), corner_radius=6).pack(side="left")
        row2 = ctk.CTkFrame(p, fg_color=BG); row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Format", width=150, anchor="w",
                     font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color=BG).pack(side="left")
        self._combo_ctk(row2, ["mp4","mkv"], self.V["rec_fmt"], 100).pack(side="left")

    def _apply_preset(self, name: str):
        p = PRESETS.get(name)
        if not p: return
        self.V["bitrate"].set(p["bitrate"]); self.V["fps"].set(p["max_fps"])
        self.V["resolution"].set(p["resolution"]); self.V["codec"].set(p["codec"])
        self.V["borderless"].set(p["borderless"]); self.V["always_top"].set(p["always_on_top"])
        self.V["stay_awake"].set(p["stay_awake"]); self.V["screen_off"].set(p["turn_screen_off"])
        self.V["fullscreen"].set(p["fullscreen"]); self.V["no_audio"].set(p["no_audio"])
        self.V["view_only"].set(p["no_control"])
        if hasattr(self, "_preset_cards"):
            for pname, (card, color) in self._preset_cards.items():
                active = pname == name
                card.configure(fg_color=color if active else CARD,
                               border_color=color if active else BDR)
                for w in card.winfo_children():
                    try:
                        w.configure(text_color="white" if active else (
                            color if w.cget("font").cget("size") >= 18 else TEXT))
                    except: pass
        self.lbl_statusbar.configure(text=f"✓ Preset: {name}")
        self.after(2000, lambda: self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN"))

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_config(self):
        c = self.cfg
        self._set_config_vars(c)
        saved_theme = c.get("theme","dark")
        self.V["theme"].set(saved_theme)
        apply_palette(saved_theme)
        self._update_mode_ui(); self._update_rtmp_hint()

    def _load_config_no_theme(self):
        c = self.cfg
        self._set_config_vars(c)
        self._update_mode_ui(); self._update_rtmp_hint()

    def _set_config_vars(self, c):
        self.V["bitrate"].set(c.get("bitrate","8M"))
        self.V["fps"].set(c.get("max_fps","60"))
        self.V["resolution"].set(c.get("resolution","(default)"))
        self.V["codec"].set(c.get("codec","h264"))
        self.V["video_encoder"].set(c.get("video_encoder","(auto)"))
        self.V["rotation"].set(c.get("rotation","0"))
        self.V["mode"].set(c.get("mode","Mirror Only"))
        self.V["rec_path"].set(c.get("record_path",os.path.expanduser("~/Videos/scrcpy")))
        self.V["rec_fmt"].set(c.get("record_format","mp4"))
        self.V["no_audio"].set(c.get("no_audio",False))
        self.V["audio_output"].set(c.get("audio_output",False))
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
        self.V["live_custom_url"].set(c.get("live_custom_url",""))
        self.V["show_floating"].set(c.get("show_floating",True))
        self.V["tcpip_port"].set(c.get("tcpip_port","5555"))
        self.V["tcpip_host"].set(c.get("tcpip_host",""))
        self.V["show_monitor"].set(c.get("show_monitor",True))
        self.V["cmd_preview_visible"].set(c.get("cmd_preview_visible",False))
        self.V["log_visible"].set(c.get("log_visible",True))
        self.V["minimize_to_tray"].set(c.get("minimize_to_tray",False))
        # preview settings
        self.V["preview_interval"].set(c.get("preview_interval","2s"))
        self.V["preview_auto_start"].set(c.get("preview_auto_start",True))

    # ── ADB ───────────────────────────────────────────────────────────────────
    def _refresh_devices(self):
        self.lbl_device_info.configure(text="Scanning...", text_color=DIM)
        self._log("$ adb devices -l")
        threading.Thread(target=self._scan_adb, daemon=True).start()

    def _on_device_selected(self, label: str):
        """Dipanggil saat user ganti device di combo — fetch encoder baru."""
        serial = self._serial_from_label(label)
        if serial and "no devices" not in serial:
            if hasattr(self, "lbl_encoder_hint"):
                self.lbl_encoder_hint.configure(text="detecting…")
            self._fetch_encoders(serial)

    def _scan_adb(self):
        devices, log = scan_devices()
        self.after(0, lambda: self._set_devices(devices, log))

    def _set_devices(self, devices, log):
        self._log(log)
        self.dev_rows = {}; self._all_devices = devices
        if not devices:
            self.combo_device.configure(values=["(no devices)"])
            self.V["device"].set("(no devices)")
            self.lbl_device_info.configure(text="Connect a device and enable USB Debugging", text_color=YEL)
            return
        labels = [label for _, label in devices]
        self.combo_device.configure(values=labels)
        self.V["device"].set(labels[0])
        count = len(devices)
        info = f"✓ {count} device(s)"
        if count > 1: info += "  —  Use Start All to mirror all devices"
        self.lbl_device_info.configure(text=info, text_color=GRN)
        self._update_start_all_btn(count)
        # Auto-fetch encoders from the first detected device
        first_serial = devices[0][0]
        if hasattr(self, "lbl_encoder_hint"):
            self.lbl_encoder_hint.configure(text="detecting…")
        self._fetch_encoders(first_serial)

    # Maps display label → raw encoder name for scrcpy
    _ENCODER_LABEL_MAP: dict = {}   # {"H.264 Software (Google)": "OMX.google.h264.encoder", ...}

    @staticmethod
    def _encoder_label(raw: str) -> str:
        """Ubah nama encoder teknis jadi label yang mudah dibaca."""
        raw_l = raw.lower()
        # Vendor
        if "google" in raw_l:       vendor = "Google"
        elif "qcom" in raw_l or "qualcomm" in raw_l: vendor = "Qualcomm"
        elif "mtk" in raw_l or "mediatek" in raw_l:  vendor = "MediaTek"
        elif "exynos" in raw_l or "samsung" in raw_l: vendor = "Samsung"
        elif "c2.android" in raw_l: vendor = "Android"
        else:                       vendor = raw.split(".")[1].capitalize() if raw.count(".")>=2 else "HW"
        # Codec
        if "h264" in raw_l or "avc" in raw_l:   codec = "H.264"
        elif "h265" in raw_l or "hevc" in raw_l: codec = "H.265"
        elif "av1" in raw_l:                      codec = "AV1"
        elif "vp8" in raw_l:                      codec = "VP8"
        elif "vp9" in raw_l:                      codec = "VP9"
        else:                                      codec = "Video"
        # SW vs HW
        if "google" in raw_l or "c2.android" in raw_l or "sw" in raw_l:
            kind = "Software"
        else:
            kind = "Hardware"
        return f"{codec} {kind} ({vendor})"

    def _fetch_encoders(self, serial: str):
        """Ambil daftar encoder dari device via scrcpy --list-encoders."""
        def _run():
            raw_list = []
            try:
                cmd = ["scrcpy", "-s", serial, "--list-encoders"]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                out = r.stdout + r.stderr
                for line in out.splitlines():
                    line = line.strip()
                    if "--video-encoder=" in line:
                        # take first word only — rest is description "(sw) (alias...)"
                        enc = line.split("--video-encoder=")[-1].strip().split()[0]
                        if enc: raw_list.append(enc)
            except: pass
            self.after(0, lambda: self._set_encoder_list(raw_list))
        threading.Thread(target=_run, daemon=True).start()

    def _set_encoder_list(self, raw_list: list):
        """Update combo dengan label simpel + simpan mapping ke raw name."""
        if not hasattr(self, "combo_encoder"): return
        # Build label map — pastikan label unik
        label_map = {"(auto)": ""}
        seen_labels: dict = {}
        for raw in raw_list:
            label = self._encoder_label(raw)
            if label in seen_labels:
                seen_labels[label] += 1
                label = f"{label} #{seen_labels[label]}"
            else:
                seen_labels[label] = 1
            label_map[label] = raw
        App._ENCODER_LABEL_MAP = label_map

        labels = list(label_map.keys())
        self.combo_encoder.configure(values=labels)

        # Preserve previous selection if still valid
        current_raw = self.V["video_encoder"].get()
        matched = next((lbl for lbl, raw in label_map.items() if raw == current_raw), None)
        self.V["video_encoder"].set(matched if matched else "(auto)")

        count = len(raw_list)
        hint = f"{count} encoder(s) found" if count > 0 else "not detected"
        if hasattr(self, "lbl_encoder_hint"):
            self.lbl_encoder_hint.configure(text=hint)

    def _update_start_all_btn(self, count: int):
        if not hasattr(self, "btn_start_all"): return
        if count > 1:
            self.btn_start_all.configure(state="normal", fg_color=GRN, hover_color="#28a745")
        else:
            self.btn_start_all.configure(state="disabled", fg_color=CARD2, hover_color=CARD2)

    # ── Build command ─────────────────────────────────────────────────────────
    def _build_cmd_for(self, serial="", idx=0, total=1, force_always_on_top=False):
        mode = self.V["mode"].get()
        cmd  = ["scrcpy"]
        if serial: cmd += ["-s", serial]
        # Per-compositor fix — inject args based on detected compositor
        _comp = detect_compositor()
        if _comp and _comp in COMPOSITOR_FIXES:
            cmd += COMPOSITOR_FIXES[_comp][0]  # extra_args
        cmd += ["--video-bit-rate", self.V["bitrate"].get()]
        cmd += ["--max-fps",        self.V["fps"].get()]
        res = self.V["resolution"].get()
        if res and res != "(default)": cmd += ["--max-size", res]
        if self.V["codec"].get() != "h264": cmd += ["--video-codec", self.V["codec"].get()]
        enc_label = self.V["video_encoder"].get()
        enc_raw = App._ENCODER_LABEL_MAP.get(enc_label, enc_label)
        if enc_raw and enc_raw != "(auto)": cmd += ["--video-encoder", enc_raw]
        if self.V["rotation"].get() != "0": cmd += ["--display-orientation", self.V["rotation"].get()]
        if mode == "Record":
            path = self.V["rec_path"].get(); fmt = self.V["rec_fmt"].get() or "mp4"
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(path, exist_ok=True)
            cmd += ["--record", os.path.join(path, f"rec_{serial}_{ts}.{fmt}")]
        if self.V["no_audio"].get():
            cmd += ["--no-audio"]
        elif self.V["audio_output"].get():
            cmd += ["--no-audio-output"]
        if force_always_on_top:
            cmd += ["--always-on-top", "--fullscreen"]
        elif total > 1:
            x, y, w, h = self._calc_tile(idx, total)
            cmd += ["--window-x",str(x),"--window-y",str(y),"--window-width",str(w),"--window-height",str(h)]
            j = self.V["win_title"].get() or "scrcpy"
            cmd += ["--window-title", f"{j} [{serial}]"]
        else:
            if self.V["fullscreen"].get(): cmd += ["--fullscreen"]
            if self.V["borderless"].get(): cmd += ["--window-borderless"]
            if self.V["always_top"].get(): cmd += ["--always-on-top"]
            j = self.V["win_title"].get()
            if j and j != "scrcpy": cmd += ["--window-title", j]
        if self.V["stay_awake"].get() and not self.V["view_only"].get(): cmd += ["--stay-awake"]
        if self.V["screen_off"].get(): cmd += ["--turn-screen-off"]
        if self.V["view_only"].get():  cmd += ["--no-control"]
        return cmd

    def _build_cmd(self, force_always_on_top=False):
        dev = self.V["device"].get()
        serial = dev.split()[0] if dev and "no devices" not in dev else ""
        return self._build_cmd_for(serial, 0, 1, force_always_on_top)

    def _preview(self):
        try:
            mode = self.V["mode"].get()
            if mode == "Livestream":
                plat = self.V["live_platform"].get()
                base = PLATFORM_RTMP.get(plat,"")
                rtmp = base+"<KEY>" if base else "<RTMP_URL>"
                br = self.V["live_bitrate"].get(); fps = self.V["live_fps"].get()
                mic = self.V["live_mic"].get(); monitor = detect_audio_monitor()
                mic_part = " \\\n  -f pulse -i default \\\n  -filter_complex amix=inputs=2" if mic else ""
                teks = (f"# scrcpy\n{' '.join(self._build_cmd(force_always_on_top=True))}\n\n"
                        f"# ffmpeg\nffmpeg -f x11grab -draw_mouse 0 \\\n"
                        f"  -framerate {fps} -r {fps} -s <screen_res> -i :0.0+0,0 \\\n"
                        f"  -f pulse -i {monitor}{mic_part} \\\n"
                        f"  -c:v libx264 -preset superfast -b:v {br} \\\n"
                        f"  -pix_fmt yuv420p -g {fps} \\\n"
                        f"  -c:a aac -b:a 128k -f flv {rtmp}")
                self._upd(self.txt_cmd_live, teks)
            self._upd(self.txt_cmd, " ".join(self._build_cmd()))
        except: pass

    def _upd(self, w, t):
        w.configure(state="normal"); w.delete("0.0","end"); w.insert("0.0", t); w.configure(state="disabled")

    def _log(self, teks):
        def _do():
            self.txt_log.configure(state="normal")
            tb = self.txt_log._textbox; tb.configure(state="normal")
            for brs in (teks+"\n").splitlines():
                bl = brs.lower()
                if brs.strip().startswith("$"):                           tag = "cmd"
                elif any(w in bl for w in ["error","fail","cannot"]):     tag = "error"
                elif any(w in bl for w in ["✓","→","found","live","start"]): tag = "ok"
                else: tag = "redup"
                tb.insert("end", brs+"\n", tag); tb.see("end")
            tb.configure(state="disabled"); self.txt_log.configure(state="disabled")
        self.after(0, _do)

    # ── Stream Preview ─────────────────────────────────────────────────────────────

    def _preview_placeholder(self):
        """Draw idle placeholder on canvas."""
        c = self.preview_canvas
        c.delete("all")
        W, H = 316, 178
        c.create_rectangle(0, 0, W, H, fill="#111111", outline="")
        # Grid lines for visual texture
        for x in range(0, W, 32):
            c.create_line(x, 0, x, H, fill="#1a1a1a", width=1)
        for y in range(0, H, 32):
            c.create_line(0, y, W, y, fill="#1a1a1a", width=1)
        # Center icon + text
        c.create_text(W//2, H//2 - 18, text="📱", font=(FN, 28), fill="#333333")
        c.create_text(W//2, H//2 + 18, text="No Preview",
                      font=(FNM, 10), fill="#444444")
        c.create_text(W//2, H//2 + 36, text="press Capture or start streaming",
                      font=(FN, 8), fill="#333333")

    def _canvas_message(self, msg: str, color: str = "#666666"):
        """Display a centered message on the preview canvas."""
        c = self.preview_canvas
        c.delete("all")
        W, H = 316, 178
        c.create_rectangle(0, 0, W, H, fill="#111111", outline="")
        c.create_text(W//2, H//2, text=msg, font=(FN, 10),
                      fill=color, justify="center")

    def _toggle_preview(self):
        """Manual capture toggle button handler."""
        if self._preview_active:
            self._stop_preview_loop()
        else:
            self._start_preview_loop(manual=True)

    def _start_preview_loop(self, manual: bool = False):
        """Begin periodic preview capture."""
        self._preview_active = True
        if manual:
            # Manual: single capture then loop at interval
            self.btn_preview_toggle.configure(
                text="■  Stop", fg_color=RED, hover_color="#cc0000",
                text_color="white", border_width=0)
            self.lbl_preview_status.configure(text="capturing…", text_color=YEL)
        self._schedule_preview_capture()

    def _stop_preview_loop(self):
        """Stop preview capture and reset canvas."""
        self._preview_active = False
        try:
            self.btn_preview_toggle.configure(
                text="📷  Capture", fg_color=CARD2, hover_color=BDR,
                text_color=DIM, border_width=1, border_color=BDR)
            self.lbl_preview_status.configure(text="idle", text_color=DIM)
            self.lbl_preview_res.configure(text="")
            if not self.live_running:
                self.lbl_preview_time.configure(text="--:--:--")
            self._preview_placeholder()
        except: pass

    def _schedule_preview_capture(self):
        """Fire off one capture thread if still active."""
        if not self._preview_active: return
        threading.Thread(target=self._do_preview_capture, daemon=True).start()

    def _do_preview_capture(self):
        """Capture one preview frame (X11 if live, ADB if idle)."""
        try:
            if self.live_running:
                # Grab from Xvfb virtual display — pass DISPLAY env + bare display string
                live_res = self.V["live_res"].get() or "1280x720"
                try:
                    rw, rh = live_res.split("x")
                    rw = int(rw) - (int(rw) % 2)
                    rh = int(rh) - (int(rh) % 2)
                except: rw, rh = 1280, 720
                xvfb_env = {**os.environ, "DISPLAY": self.xvfb_display}
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "x11grab", "-framerate", "1",
                    "-s", f"{rw}x{rh}", "-i", f"{self.xvfb_display}+0,0",
                    "-vframes", "1", "-vf", "scale=316:-2",
                    PREVIEW_TMP
                ]
                r = subprocess.run(cmd, capture_output=True, timeout=10, env=xvfb_env)
                if r.returncode == 0 and os.path.exists(PREVIEW_TMP):
                    self.after(0, lambda: self._update_preview_canvas(PREVIEW_TMP, source="x11"))
                else:
                    err = r.stderr.decode(errors="replace").strip().splitlines()
                    last = err[-1] if err else "unknown error"
                    self.after(0, lambda e=last: self._canvas_message("Grab failed: " + e, RED))
            else:
                # Grab from device via ADB
                dev = self.V["device"].get()
                if not dev or "no devices" in dev:
                    self.after(0, lambda: self._canvas_message("No device\nconnected"))
                    self._preview_active = False
                    self.after(0, self._stop_preview_loop)
                    return
                serial = dev.split()[0]
                r = subprocess.run(
                    ["adb", "-s", serial, "exec-out", "screencap", "-p"],
                    capture_output=True, timeout=12)
                if r.returncode == 0 and r.stdout:
                    with open(PREVIEW_TMP, "wb") as f: f.write(r.stdout)
                    self.after(0, lambda: self._update_preview_canvas(PREVIEW_TMP, source="adb"))
                else:
                    ok, message = capture_device_preview(serial, PREVIEW_TMP)
                    if ok:
                        self.after(0, lambda: self._update_preview_canvas(PREVIEW_TMP, source="adb"))
                    else:
                        self.after(0, lambda: self._canvas_message("ADB screenshot\nfailed", RED))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self._canvas_message("Capture timeout", YEL))
        except Exception as e:
            self.after(0, lambda err=e: self._canvas_message(f"Error:\n{err}", RED))

        # Schedule next capture if still active
        if self._preview_active:
            try:
                ms = int(self.V["preview_interval"].get().replace("s","")) * 1000
            except: ms = 2000
            self.after(ms, self._schedule_preview_capture)

    def _update_preview_canvas(self, path: str, source: str = "adb"):
        """Load image from path and draw onto preview_canvas."""
        if not os.path.exists(path): return
        CW, CH = 316, 178
        try:
            c = self.preview_canvas
            c.delete("all")
            c.create_rectangle(0, 0, CW, CH, fill="#000000", outline="")

            if PIL_OK:
                img = Image.open(path).convert("RGB")
                # Scale to fit 316×178, preserving aspect ratio (letterbox/pillarbox)
                img.thumbnail((CW, CH), Image.LANCZOS)  # type: ignore
                iw, ih = img.size
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
                iw, ih = photo.width(), photo.height()
                if iw > CW or ih > CH:
                    scale = max(iw / CW, ih / CH)
                    subsample = max(1, math.ceil(scale))
                    photo = photo.subsample(subsample, subsample)  # type: ignore
                    iw, ih = photo.width(), photo.height()

            self._preview_img_ref = photo  # prevent GC
            x_off = (CW - iw) // 2
            y_off = (CH - ih) // 2
            c.create_image(x_off, y_off, anchor="nw", image=photo)

            # Source badge (top-left)
            badge_text = "🔴 LIVE" if source == "x11" else "📱 ADB"
            badge_color = RED if source == "x11" else ACC
            c.create_rectangle(4, 4, 72, 18, fill="#000000", stipple="gray50", outline="")
            c.create_text(38, 11, text=badge_text, font=(FNM, 7, "bold"),
                          fill=badge_color, anchor="center")

            # Update stats labels
            self.lbl_preview_res.configure(text=f"{iw}×{ih}")
            status_text = "live" if source == "x11" else "adb"
            self.lbl_preview_status.configure(text=status_text,
                text_color=RED if source == "x11" else ACC)
        except Exception as e:
            self._canvas_message(f"Load error:\n{e}", RED)

    # ── Elapsed timer (runs independently of preview) ─────────────────────────
    def _start_elapsed_timer(self):
        """Start the elapsed timer when live begins."""
        self._preview_start_time = time.time()
        self._tick_elapsed()

    def _tick_elapsed(self):
        """Update elapsed time label every second while live is running."""
        if not self.live_running:
            try: self.lbl_preview_time.configure(text="--:--:--", text_color=DIM)
            except: pass
            return
        if self._preview_start_time:
            elapsed = int(time.time() - self._preview_start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            try:
                self.lbl_preview_time.configure(
                    text=f"{h:02d}:{m:02d}:{s:02d}", text_color=RED)
            except: pass
        self.after(1000, self._tick_elapsed)

    # ── Toggle/Start/Stop ─────────────────────────────────────────────────────
    def _toggle(self):
        if self.live_running: self._stop(); return
        if len(self.running_devs) > 1: self._stop_all(); return
        dev = self.V["device"].get()
        if not dev or "no devices" in dev:
            messagebox.showwarning("No Device","Select a device first!"); return
        serial = self._serial_from_label(dev)
        if not serial: return
        if self.V["mode"].get() == "Livestream":
            # Dep gate only for Livestream — requires ffmpeg, xdotool, pactl
            missing = getattr(self, "_missing_deps", set())
            live_deps = missing & {"ffmpeg","xdotool","pactl","scrcpy"}
            if live_deps:
                self._dep_gate_popup(list(live_deps)); return
            self.V["device"].set(dev); self._start_live()
        else:
            self._toggle_device(serial)

    def _start_all(self):
        if not self._all_devices:
            messagebox.showwarning("No Devices","No devices found!"); return
        total = len(self._all_devices)
        for idx, (serial, label) in enumerate(self._all_devices):
            if serial not in self.running_devs:
                self._start_device_tiled(serial, idx, total)
        self.btn_start_all.configure(text="■  Stop All", command=self._stop_all,
                                      fg_color=RED, hover_color="#cc0000", state="normal")

    def _stop_all(self):
        for serial in list(self.running_devs): self._stop_device(serial)
        self.btn_start_all.configure(text="▶▶  All", command=self._start_all,
                                      fg_color=GRN, hover_color="#28a745")

    def _serial_from_label(self, label: str) -> str:
        for serial, lbl in self._all_devices:
            if lbl == label: return serial
        return label.split()[0] if label else ""

    def _start_device_tiled(self, serial: str, idx: int, total: int, _retry_encoder: str = ""):
        cmd = self._build_cmd_for(serial, idx, total)
        # If retrying with a specific encoder, inject --video-encoder
        if _retry_encoder:
            cmd += ["--video-encoder", _retry_encoder]
            label = App._encoder_label(_retry_encoder)
            self._log(f"→ Retrying with: {label} ({_retry_encoder})")
        self._log(f"\n$ {' '.join(cmd)}")
        try:
            # Per-compositor env override
            _comp_env = {}
            _comp = detect_compositor()
            if _comp and _comp in COMPOSITOR_FIXES:
                _comp_env = COMPOSITOR_FIXES[_comp][1]
            proc_env = {**os.environ, **_comp_env} if _comp_env else None
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, env=proc_env)
            self.processes[serial] = proc
            self.running_devs.add(serial)
            self._proc_start_times = getattr(self, "_proc_start_times", {})
            self._proc_start_times[serial] = time.time()
            self._update_header_status()
            if len(self.running_devs) > 1:
                self.V["fullscreen"].set(False); self.V["borderless"].set(False)
            threading.Thread(target=self._read_device_output, args=(serial,proc), daemon=True).start()
            threading.Thread(target=self._wait_device_process, args=(serial,proc,_retry_encoder), daemon=True).start()
        except FileNotFoundError: messagebox.showerror("Error","scrcpy not found!")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _toggle_device(self, serial: str):
        if serial in self.running_devs: self._stop_device(serial)
        else: self._start_device_tiled(serial, len(self.running_devs), max(len(self.running_devs)+1,1))

    def _calc_tile(self, idx: int, total: int):
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight() - 80
        if total == 1:   return sw//4, 40, sw//2, int(sh*0.8)
        elif total == 2: return idx*(sw//2), 40, sw//2, sh
        elif total == 3: return idx*(sw//3), 40, sw//3, sh
        elif total == 4: return (idx%2)*(sw//2), 40+(idx//2)*(sh//2), sw//2, sh//2
        else:            return (idx%3)*(sw//3), 40+(idx//3)*(sh//2), sw//3, sh//2

    def _stop_device(self, serial: str):
        proc = self.processes.pop(serial, None)
        if proc:
            try: proc.terminate()
            except: pass
        self.running_devs.discard(serial)
        self._update_header_status()
        self._log(f"→ Stopped: {serial}\n")

    def _update_header_status(self):
        n = len(self.running_devs)
        dev = self.V["device"].get()
        selected_serial = self._serial_from_label(dev) if dev and "no devices" not in dev else ""
        selected_running = selected_serial in self.running_devs
        if n == 0:
            self.lbl_status.configure(text="● Ready", text_color=DIM, fg_color=CARD2)
            self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN")
            self.btn_start.configure(text="▶  Start", fg_color=ACC, hover_color="#0060cc")
            self.float_btn_toggle.configure(text="▶", text_color=GRN)
            self.running = False
            if hasattr(self, "btn_start_all"):
                connected = len(self._all_devices)
                self.btn_start_all.configure(
                    text="▶▶  All", command=self._start_all,
                    fg_color=GRN if connected > 1 else CARD2,
                    hover_color="#28a745" if connected > 1 else CARD2,
                    state="normal" if connected > 1 else "disabled")
        else:
            self.lbl_status.configure(
                text=f"● Mirroring  {n} device(s)", text_color=GRN, fg_color=CARD2)
            self.lbl_statusbar.configure(text=f"● {n} device(s) active")
            self.running = True
            if selected_running:
                self.btn_start.configure(text="■  Stop", fg_color=RED, hover_color="#cc0000")
            else:
                self.btn_start.configure(text="▶  Start", fg_color=ACC, hover_color="#0060cc")
            self.float_btn_toggle.configure(text="■", text_color=RED)

    def _read_device_output(self, serial: str, proc):
        # stdout dibaca di _wait_device_process — skip di sini
        pass

    def _wait_device_process(self, serial: str, proc, _used_encoder: str = ""):
        start = getattr(self, "_proc_start_times", {}).get(serial, time.time())
        # Collect output to detect MediaCodec errors
        output_lines = []
        try:
            for line in proc.stdout:
                output_lines.append(line.rstrip())
        except: pass
        proc.wait()
        elapsed = time.time() - start
        full_output = "\n".join(output_lines)
        for ln in output_lines: self._log(f"[{serial}] {ln}")
        # Fast crash (<8 detik) + MediaCodec error + belum pernah retry
        is_codec_err = "MediaCodec" in full_output or "CodecException" in full_output
        if elapsed < 8 and is_codec_err and not _used_encoder:
            self._log("⚠ MediaCodec error detected — retrying with OMX.google.h264.encoder…")
            self.after(0, lambda: self._codec_fallback(serial))
        else:
            self.after(0, lambda: self._on_device_stopped(serial))

    def _codec_fallback(self, serial: str):
        """Auto-retry dengan software encoder setelah MediaCodec crash."""
        self.processes.pop(serial, None)
        self.running_devs.discard(serial)
        fallback_raw = "OMX.google.h264.encoder"
        fallback_label = App._encoder_label(fallback_raw)
        # Update label map & dropdown if not already present
        if hasattr(self, "combo_encoder"):
            if fallback_label not in App._ENCODER_LABEL_MAP:
                App._ENCODER_LABEL_MAP[fallback_label] = fallback_raw
                vals = list(self.combo_encoder.cget("values"))
                if fallback_label not in vals:
                    vals.insert(1, fallback_label)
                    self.combo_encoder.configure(values=vals)
            self.V["video_encoder"].set(fallback_label)
        idx = len(self.running_devs)
        total = max(len(self._all_devices), 1)
        self._start_device_tiled(serial, idx, total, _retry_encoder=fallback_raw)

    def _on_device_stopped(self, serial: str):
        if serial in self.running_devs:
            self.processes.pop(serial, None); self.running_devs.discard(serial)
            self._update_header_status(); self._log(f"→ {serial} disconnected\n")

    def _start_live(self):
        dev = self.V["device"].get()
        if not dev or "no devices" in dev:
            messagebox.showwarning("No Device","Select a device first!"); return
        key = self.V["live_key"].get().strip()
        if not key:
            messagebox.showwarning("Missing Stream Key","Enter Stream Key first!"); return
        plat = self.V["live_platform"].get(); base = PLATFORM_RTMP.get(plat,"")
        key  = self.V["live_key"].get().strip()
        if plat == "Custom":
            custom_url = self.V["live_custom_url"].get().strip()
            if not custom_url:
                messagebox.showwarning("Missing RTMP URL","Enter Custom RTMP URL first!"); return
            rtmp_url = custom_url.rstrip("/")+"/"+key if key else custom_url
        else: rtmp_url = base + key

        # ── Xvfb: scrcpy runs on virtual display, main screen stays free ─────
        live_res = self.V["live_res"].get() or "1280x720"
        xvfb_cmd = ["Xvfb", self.xvfb_display, "-screen", "0", f"{live_res}x24"]
        self._log(f"$ {' '.join(xvfb_cmd)}")
        try:
            self.xvfb_proc = subprocess.Popen(
                xvfb_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(0.6)
            self._log(f"→ Xvfb started on {self.xvfb_display} ({live_res})")
        except FileNotFoundError:
            messagebox.showerror("Error","Xvfb not found!\nsudo apt install xvfb"); return
        except Exception as e:
            messagebox.showerror("Error", f"Xvfb failed: {e}"); return

        # scrcpy on virtual display — no need for fullscreen/always-on-top
        scrcpy_cmd = self._build_cmd(force_always_on_top=False)
        scrcpy_env = {**os.environ, "DISPLAY": self.xvfb_display}
        # Per-compositor env override (e.g. SDL_VIDEODRIVER=x11 for GNOME/KDE)
        _comp = detect_compositor()
        if _comp and _comp in COMPOSITOR_FIXES:
            scrcpy_env.update(COMPOSITOR_FIXES[_comp][1])
        self._log(f"$ DISPLAY={self.xvfb_display} {' '.join(scrcpy_cmd)}")
        try:
            self.process = subprocess.Popen(
                scrcpy_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=scrcpy_env)
            self.running = True; self.live_running = True
            self._ui_set_running(label="■   Stop Live", color=RED)
            self._log("→ Waiting for scrcpy on virtual display...")
            threading.Thread(target=self._wait_process_window_lalu_live, args=(rtmp_url,plat), daemon=True).start()
            threading.Thread(target=self._wait_process, daemon=True).start()
            self._start_elapsed_timer()
            if self.V["preview_auto_start"].get():
                self.after(3000, lambda: self._start_preview_loop(manual=False))
        except FileNotFoundError: messagebox.showerror("Error","scrcpy not found!")
        except Exception as e: messagebox.showerror("Error", str(e))

    def _wait_process_window_lalu_live(self, rtmp_url, plat):
        # Tunggu scrcpy muncul di virtual display
        win_id = None
        xenv = {**os.environ, "DISPLAY": self.xvfb_display}
        for _ in range(20):
            try:
                r = subprocess.run(
                    ["xdotool","search","--class","scrcpy"],
                    capture_output=True, text=True, timeout=2, env=xenv)
                if r.returncode==0 and r.stdout.strip():
                    win_id = r.stdout.strip().splitlines()[0]; break
            except FileNotFoundError: self._log("ERROR: xdotool not found!"); return
            except: pass
            time.sleep(0.5)
        if not win_id: self._log("ERROR: scrcpy not found on virtual display"); return

        # Resolusi = live_res (sama persis ukuran Xvfb)
        live_res = self.V["live_res"].get() or "1280x720"
        try:
            rw, rh = live_res.split("x")
            rw = int(rw) - (int(rw) % 2)
            rh = int(rh) - (int(rh) % 2)
        except: rw, rh = 1280, 720

        br  = self.V["live_bitrate"].get(); fps = self.V["live_fps"].get()
        bufsize = str(int(br.replace("k",""))*2)+"k"; gop = str(int(fps))
        monitor = detect_audio_monitor()

        # ffmpeg grabs from virtual display :99 — not the main screen :0
        ffmpeg_cmd = [
            "ffmpeg","-y","-f","x11grab","-draw_mouse","0",
            "-framerate",fps,"-r",fps,"-s",f"{rw}x{rh}",
            "-i",f"{self.xvfb_display}.0+0,0",
            "-thread_queue_size","4096","-f","pulse","-ac","2","-i",monitor,
            *([ "-thread_queue_size","4096","-f","pulse","-ac","2","-i","default",
                "-filter_complex","amix=inputs=2:duration=first:dropout_transition=0"
              ] if self.V["live_mic"].get() else []),
            "-threads","2","-c:v","libx264","-preset","superfast","-tune","zerolatency",
            "-b:v",br,"-maxrate",br,"-bufsize",bufsize,"-pix_fmt","yuv420p","-g",gop,
            "-af","aresample=48000:resampler=soxr",
            "-c:a","aac","-b:a","128k","-ar","48000","-f","flv",rtmp_url,
        ]
        self._log(f"$ {' '.join(ffmpeg_cmd)}")
        try:
            self.ffmpeg_proc = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            threading.Thread(target=self._read_ffmpeg_log, daemon=True).start()
            threading.Thread(target=self._wait_ffmpeg_proc, daemon=True).start()
            self._log(f"→ Live started to {plat}! 🔴  [{rw}×{rh}] virtual display")
            self.tabview.set("🔴  Livestream")
        except Exception as e: self._log(f"ERROR ffmpeg: {e}")

    def _read_ffmpeg_log(self):
        if not self.ffmpeg_proc or not self.ffmpeg_proc.stderr: return
        for baris in self.ffmpeg_proc.stderr:
            baris = baris.decode(errors="replace").rstrip()
            if any(k in baris.lower() for k in ["fps=","bitrate=","error","failed","speed="]):
                self._log(f"[ffmpeg] {baris}")

    def _wait_ffmpeg_proc(self):
        if self.ffmpeg_proc: self.ffmpeg_proc.wait()
        if self.live_running:
            self._log("→ ffmpeg stopped"); self.after(0, self._sudah_stop)

    def _ui_set_running(self, label="■   Stop", color=RED):
        self.btn_start.configure(text=label, fg_color=color, hover_color="#cc0000")
        # Also update the livestream tab button if in Livestream mode
        mode = self.V["mode"].get()
        if mode == "Livestream" and hasattr(self, "btn_start_live"):
            self.btn_start_live.configure(text="■   Stop Livestream", fg_color=RED, hover_color="#cc0000")
        pid  = self.process.pid if self.process else "?"
        st   = f"🔴 LIVE  pid:{pid}" if mode=="Livestream" else f"● {mode}  pid:{pid}"
        self.lbl_status.configure(text=st, text_color=RED if mode=="Livestream" else GRN, fg_color=CARD2)
        self.lbl_statusbar.configure(text=st)
        self.float_btn_toggle.configure(text="■", text_color=RED)
        if mode == "Livestream": self._float_live_mode(True)

    def _read_output(self):
        if self.process and self.process.stdout:
            for brs in self.process.stdout: self._log(brs.rstrip())

    def _wait_process(self):
        if self.process: self.process.wait()
        self.after(0, self._sudah_stop)

    def _stop(self):
        # Terminate tracked processes
        for proc in [self.ffmpeg_proc, self.process, self.xvfb_proc]:
            if proc:
                try: proc.terminate()
                except: pass
        for proc in self.processes.values():
            try: proc.terminate()
            except: pass
        self.processes.clear(); self.running_devs.clear()
        # Kill any orphan ffmpeg/scrcpy/Xvfb by current user to avoid doubles
        self._kill_orphans()
        self.after(100, self._refresh_devices)
        self._sudah_stop(); self._update_header_status()

    def _kill_orphans(self):
        """Kill any lingering ffmpeg/Xvfb/scrcpy processes spawned by this session."""
        import signal
        targets = ["ffmpeg", f"Xvfb {self.xvfb_display}"]
        try:
            r = subprocess.run(["ps", "-u", os.environ.get("USER", ""), "-o", "pid,args", "--no-headers"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                line = line.strip()
                pid_str = line.split()[0] if line else ""
                if not pid_str.isdigit(): continue
                pid = int(pid_str)
                if pid == os.getpid(): continue  # jangan kill diri sendiri
                # Kill ffmpeg processes streaming to RTMP (not preview /tmp/)
                if "ffmpeg" in line and "rtmp://" in line:
                    try: os.kill(pid, signal.SIGTERM)
                    except: pass
                # Kill Xvfb virtual display milik kita
                elif f"Xvfb {self.xvfb_display}" in line:
                    try: os.kill(pid, signal.SIGTERM)
                    except: pass
        except: pass

    def _sudah_stop(self):
        self.running = self.live_running = False
        self.process = self.ffmpeg_proc = self.xvfb_proc = None
        mode  = self.V["mode"].get()
        label = "▶  Start Live" if mode=="Livestream" else "▶  Start"
        try: self.btn_start.configure(text=label, fg_color=ACC, hover_color="#0060cc")
        except: pass
        # Also update the livestream tab button if in Livestream mode
        if mode == "Livestream" and hasattr(self, "btn_start_live"):
            self.btn_start_live.configure(text="🔴  Start Livestream", fg_color=RED, hover_color="#cc0000")
        self.lbl_status.configure(text="● Ready", text_color=DIM, fg_color=CARD2)
        self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN")
        self._log("→ stopped\n")
        self.float_btn_toggle.configure(text="▶", text_color=GRN)
        self._float_live_mode(False)
        # ── Stop preview when live ends ──────────────────────────────────────
        self._stop_preview_loop()
        if hasattr(self, "btn_start_all"):
            connected = len(self._all_devices)
            self.btn_start_all.configure(
                text="▶▶  All", command=self._start_all,
                fg_color=GRN if connected > 1 else CARD2,
                hover_color="#28a745" if connected > 1 else CARD2,
                state="normal" if connected > 1 else "disabled")

    # ── Device Monitor ────────────────────────────────────────────────────────
    def _start_monitor_loop(self):
        self._build_monitor()
        self._monitor_running = self.V["show_monitor"].get()
        self._poll_monitor()

    def _build_monitor(self):
        self.monitor_win = ctk.CTkToplevel(self)
        mw = self.monitor_win
        mw.overrideredirect(True); mw.attributes("-topmost", True)
        mw.configure(fg_color=CARD)
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        mw.geometry(f"180x172+{sw-196}+{sh-230}")

        hdr = tk.Frame(mw, bg=CARD2, height=22); hdr.pack(fill="x"); hdr.pack_propagate(False)
        tk.Label(hdr, text="📊 Monitor", bg=CARD2, fg=DIM, font=(FN,8,"bold")).pack(side="left", padx=8)
        hdr.bind("<ButtonPress-1>", lambda e: setattr(self,"_mx",e.x) or setattr(self,"_my",e.y))
        hdr.bind("<B1-Motion>", lambda e: mw.geometry(
            f"+{mw.winfo_x()+e.x-self._mx}+{mw.winfo_y()+e.y-self._my}"))

        body = ctk.CTkFrame(mw, fg_color=CARD, corner_radius=0)
        body.pack(fill="both", expand=True, padx=6, pady=4)
        self.mon_labels = {}
        for key, icon, label in [
            ("battery","🔋","Battery"),("temp","🌡","Temp"),
            ("ram","🧠","RAM"),("cpu","⚡","CPU"),
            ("ping","🌐","Ping"),("net","↕","Network"),
        ]:
            row = ctk.CTkFrame(body, fg_color="transparent"); row.pack(fill="x", pady=1)
            ctk.CTkLabel(row, text=f"{icon} {label}", font=ctk.CTkFont(FN,FS(9)),
                         text_color=DIM, fg_color="transparent", width=72, anchor="w").pack(side="left")
            lbl = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(FNM,FS(9),"bold"),
                               text_color=TEXT, fg_color="transparent", anchor="e")
            lbl.pack(side="right")
            self.mon_labels[key] = lbl

        if not hasattr(self, "_prev_net"): self._prev_net = None
        if not self.V["show_monitor"].get(): mw.withdraw()

    def _poll_monitor(self):
        try:
            if not self.winfo_exists(): return
        except: return
        if self.V["show_monitor"].get():
            dev = self.V["device"].get()
            if dev and "no devices" not in dev and "Scanning" not in dev:
                serial = dev.split()[0]
                threading.Thread(target=self._fetch_stats, args=(serial,), daemon=True).start()
        self.after(5000, self._poll_monitor)

    def _fetch_stats(self, serial: str):
        stats, self._prev_net = fetch_device_stats(serial, self._prev_net)
        self.after(0, lambda: self._update_monitor_ui(stats))

    def _update_monitor_ui(self, stats: dict):
        if not hasattr(self, "mon_labels"): return
        for key, val in stats.items():
            if key not in self.mon_labels: continue
            color = TEXT
            if key == "battery":
                try: pct = int(val.replace("%","")); color = RED if pct<20 else YEL if pct<50 else GRN
                except: pass
            elif key == "temp":
                try: t = float(val.replace("°C","")); color = GRN if t<40 else YEL if t<55 else RED
                except: pass
            elif key == "cpu":
                try: pct = float(val.replace("%","")); color = GRN if pct<50 else YEL if pct<80 else RED
                except: pass
            elif key == "ping":
                try: ms = float(val.replace("ms","")); color = GRN if ms<50 else YEL if ms<150 else RED
                except: pass
            self.mon_labels[key].configure(text=val, text_color=color)

    # ── TCP/IP ────────────────────────────────────────────────────────────────
    def _log_tcpip(self, text, tag="info"):
        def _do():
            self.txt_tcpip.configure(state="normal")
            tb = self.txt_tcpip._textbox; tb.configure(state="normal")
            tb.insert("end", text+"\n", tag); tb.see("end")
            tb.configure(state="disabled"); self.txt_tcpip.configure(state="disabled")
        self.after(0, _do)

    def _enable_tcpip(self):
        port = self.V["tcpip_port"].get().strip() or "5555"
        self._log_tcpip(f"$ adb tcpip {port}", "info")
        def _run():
            ok, message = enable_tcpip(port)
            if ok:
                self._log_tcpip(f"✓ {message}", "ok")
                self._log_tcpip("→ Now disconnect USB and enter device IP below", "info")
            else:
                self._log_tcpip(f"Error: {message}", "error")
        threading.Thread(target=_run, daemon=True).start()

    def _auto_detect_ip(self):
        serial = None
        for s in list(self.running_devs) + list(self.processes.keys()):
            if "." not in s:
                serial = s
                break
        if not serial:
            dev = self.V["device"].get()
            if dev and "no devices" not in dev:
                serial = dev.split()[0]
        if not serial:
            self._log_tcpip("Error: No USB device connected!", "error")
            return
        self._log_tcpip(f"$ adb -s {serial} shell ip addr show wlan0", "info")
        def _run():
            ok, message = detect_device_ip(serial)
            if ok:
                self.after(0, lambda: self.V["tcpip_host"].set(message))
                self._log_tcpip(f"✓ Found IP: {message}", "ok")
            else:
                self._log_tcpip(f"Error: {message}", "error")
        threading.Thread(target=_run, daemon=True).start()
    def _check_deps_startup(self):
        def _run():
            missing = check_dependencies()
            optional_missing = check_optional_dependencies()
            if missing:
                self.after(0, lambda: self._show_dep_warning(missing))
            elif optional_missing:
                self.after(0, lambda: self._show_optional_dep_warning(optional_missing))
        threading.Thread(target=_run, daemon=True).start()
        self.after(600, self._recheck_deps)

    def _show_optional_dep_warning(self, missing: list):
        if "pillow" in missing:
            self.lbl_status.configure(
                text="⚠ Pillow optional missing", text_color=YEL, fg_color=CARD2)

    def _on_tab_change(self, *_):
        """Handle tab changes and adjust mode accordingly."""
        try:
            current_tab = self.tabview.get()
            current_mode = self.V["mode"].get()

            if "📱  Mirror" in current_tab:
                # When switching to Mirror tab, ensure mode is not Livestream
                if current_mode == "Livestream":
                    self._set_mode("Mirror Only")
            elif "🔴  Livestream" in current_tab:
                # When switching to Livestream tab, set mode to Livestream
                if current_mode != "Livestream":
                    self.V["mode"].set("Livestream")
                    self._update_mode_ui()  # Update UI for Livestream mode
        except: pass

    def _show_deps_popup(self):
        """Popup lengkap semua dependencies + status + install hint."""
        ALL_DEPS = [
            ("scrcpy",   "Android screen cast",     "sudo apt install scrcpy",           True),
            ("adb",      "Android Debug Bridge",    "sudo apt install adb",              True),
            ("ffmpeg",   "Stream encoder",          "sudo apt install ffmpeg",           True),
            ("xdotool",  "Window detection",        "sudo apt install xdotool",          True),
            ("pactl",    "PipeWire / PulseAudio",   "sudo apt install pulseaudio-utils", True),
            ("Xvfb",     "Virtual display (live)",  "sudo apt install xvfb",             True),
            ("xrandr",   "HiDPI detection",         "sudo apt install x11-xserver-utils",True),
            ("pillow",   "Stream preview canvas",   "pip install pillow",                False),  # optional
        ]

        popup = ctk.CTkToplevel(self)
        popup.title("Dependencies")
        popup.configure(fg_color=BG)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)

        pw, ph = 520, 560  # fixed height, scrollable
        sx = self.winfo_x() + (self.winfo_width()  - pw) // 2
        sy = self.winfo_y() + (self.winfo_height() - ph) // 2
        popup.geometry(f"{pw}x{ph}+{sx}+{sy}")
        popup.update_idletasks()
        popup.after(100, popup.grab_set)

        # Header
        hdr = ctk.CTkFrame(popup, fg_color=CARD, corner_radius=0, height=46)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="📦  Dependencies",
            font=ctk.CTkFont(FN,FS(13),"bold"), text_color=TEXT,
            fg_color="transparent").pack(side="left", padx=16)
        ctk.CTkLabel(hdr, text="Required & optional tools",
            font=ctk.CTkFont(FN,FS(9)), text_color=DIM,
            fg_color="transparent").pack(side="left")

        # Scrollable body
        scroll = ctk.CTkScrollableFrame(popup, fg_color=BG, corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=0, pady=0)
        body = ctk.CTkFrame(scroll, fg_color=BG)
        body.pack(fill="both", expand=True, padx=16, pady=(10,0))

        dot_refs = {}

        for name, desc, install_cmd, required in ALL_DEPS:
            row = ctk.CTkFrame(body, fg_color=CARD2, corner_radius=8,
                               border_width=1, border_color=BDR)
            row.pack(fill="x", pady=4)

            # Dot status
            dot = ctk.CTkLabel(row, text="●", font=ctk.CTkFont(FN,FS(12),"bold"),
                               text_color=DIM, fg_color="transparent", width=28)
            dot.pack(side="left", padx=(10,0), pady=8)

            # Name
            badge = "required" if required else "optional"
            badge_color = DIM if required else YEL
            ctk.CTkLabel(row, text=name, font=ctk.CTkFont(FNM,FS(10),"bold"),
                         text_color=ACC, fg_color="transparent",
                         width=72, anchor="w").pack(side="left", padx=(6,0))

            # Desc + install cmd
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=8)
            ctk.CTkLabel(info, text=desc, font=ctk.CTkFont(FN,FS(9)),
                         text_color=TEXT, fg_color="transparent",
                         anchor="w").pack(anchor="w", pady=(6,0))
            ctk.CTkLabel(info, text=install_cmd, font=ctk.CTkFont(FNM,FS(8)),
                         text_color=ACC, fg_color="transparent",
                         anchor="w").pack(anchor="w", pady=(0,6))

            ctk.CTkLabel(row, text=badge, font=ctk.CTkFont(FN,FS(7)),
                         text_color=badge_color, fg_color="transparent",
                         width=56, anchor="e").pack(side="right", padx=(0,10))

            dot_refs[name] = dot

        # Tombol bawah
        btn_row = ctk.CTkFrame(popup, fg_color=BG)
        btn_row.pack(fill="x", padx=16, pady=12)

        def _check_all():
            # Set semua ke checking
            for dot in dot_refs.values():
                dot.configure(text_color=YEL)
            def _run():
                ok_count = 0
                for name, desc, install_cmd, required in ALL_DEPS:
                    # Command check per tool
                    CHECK_CMDS = {
                        "scrcpy":  ["scrcpy","--version"],
                        "adb":     ["adb","version"],
                        "ffmpeg":  ["ffmpeg","-version"],
                        "xdotool": ["xdotool","version"],
                        "pactl":   ["pactl","--version"],
                        "Xvfb":    ["Xvfb","-help"],
                        "xrandr":  ["xrandr","--version"],
                        "pillow":  None,
                    }
                    if name == "pillow":
                        ok = PIL_OK
                    else:
                        cmd_check = CHECK_CMDS.get(name, [name,"--version"])
                        try:
                            r = subprocess.run(cmd_check,
                                capture_output=True, timeout=5)
                            ok = True  # no FileNotFoundError means installed
                        except FileNotFoundError: ok = False
                        except: ok = True
                    if ok: ok_count += 1
                    color = GRN if ok else (YEL if not required else RED)
                    self.after(0, lambda d=name, c=color: dot_refs[d].configure(text_color=c))
                total = len(ALL_DEPS)
                summary = f"✓ {ok_count}/{total} installed"
                self.after(0, lambda: self._dep_summary_lbl.configure(
                    text=summary,
                    text_color=GRN if ok_count==total else YEL))
            threading.Thread(target=_run, daemon=True).start()

        ctk.CTkButton(btn_row, text="↺  Check All", command=_check_all,
            height=32, fg_color=ACC, hover_color="#0060cc",
            text_color="white", font=ctk.CTkFont(FN,FS(10),"bold"),
            corner_radius=8).pack(side="left", padx=(0,8))

        ctk.CTkButton(btn_row, text="Close",
            command=lambda: [popup.grab_release(), popup.destroy()],
            height=32, fg_color=CARD, hover_color=CARD2,
            text_color=DIM, font=ctk.CTkFont(FN,FS(10)),
            border_width=1, border_color=BDR, corner_radius=8).pack(side="right")

        # Auto check saat popup dibuka
        popup.after(300, _check_all)

    def _recheck_deps(self):
        """Legacy — sekarang cukup buka popup."""
        self._show_deps_popup()

    def _fetch_all_dep_versions(self):
        DEP_CMDS = {
            "scrcpy":  (["scrcpy","--version"],   r"scrcpy\s+([\d.]+)"),
            "ffmpeg":  (["ffmpeg","-version"],     r"ffmpeg version ([\S]+)"),
            "adb":     (["adb","version"],         r"Android Debug Bridge version ([\d.]+)"),
            "xdotool": (["xdotool","version"],     r"([\d.]+)"),
            "pactl":   (["pactl","--version"],     r"pactl ([\S]+)"),
        }
        results = {}
        for name, (cmd, pattern) in DEP_CMDS.items():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                out = r.stdout + r.stderr
                m = re.search(pattern, out, re.IGNORECASE)
                results[name] = ("ok", m.group(1) if m else "found")
            except FileNotFoundError: results[name] = ("missing", "not found")
            except Exception:         results[name] = ("err", "error")
        self.after(0, lambda: self._update_dep_ui(results))

    def _update_dep_ui(self, results: dict):
        if not hasattr(self, "_dep_rows"): return
        for name, (status, ver) in results.items():
            if name not in self._dep_rows: continue
            lbl_ver, lbl_status = self._dep_rows[name]
            if status == "ok":
                lbl_ver.configure(text=ver, text_color=DIM)
                lbl_status.configure(text="●", text_color=GRN)
            else:
                lbl_ver.configure(text="not installed", text_color=RED)
                lbl_status.configure(text="●", text_color=RED)
        if hasattr(self, "btn_recheck_deps"):
            self.btn_recheck_deps.configure(state="normal", text="↺ Check")

    def _show_dep_warning(self, missing: list):
        """Popup custom CTk — list dep satu per satu, blokir Start kalau ada yang missing."""
        self._missing_deps = set(missing)
        self.lbl_status.configure(text=f"⚠ Missing deps", text_color=YEL, fg_color=CARD2)
        self._dep_gate_popup(missing)

    def _dep_gate_popup(self, missing: list):
        """Modal popup bergaya CTk — satu baris per dependency, tombol install & re-check."""
        hints = {
            "scrcpy":  "sudo apt install scrcpy",
            "adb":     "sudo apt install adb",
            "ffmpeg":  "sudo apt install ffmpeg",
            "xdotool": "sudo apt install xdotool",
            "pactl":   "sudo apt install pulseaudio-utils",
            "xvfb":    "sudo apt install xvfb",
        }
        popup = ctk.CTkToplevel(self)
        popup.title("Dependencies Required")
        popup.configure(fg_color=BG)
        popup.resizable(False, False)
        popup.attributes("-topmost", True)
        popup.grab_set()  # modal

        # Center popup
        popup.update_idletasks()
        pw, ph = 420, 60 + len(missing) * 52 + 80
        sx = self.winfo_x() + (self.winfo_width() - pw) // 2
        sy = self.winfo_y() + (self.winfo_height() - ph) // 2
        popup.geometry(f"{pw}x{ph}+{sx}+{sy}")

        # Header
        hdr = ctk.CTkFrame(popup, fg_color=CARD, corner_radius=0, height=48)
        hdr.pack(fill="x"); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="⚠  Missing Dependencies",
            font=ctk.CTkFont(FN,FS(13),"bold"), text_color=YEL,
            fg_color="transparent").pack(side="left", padx=16, pady=12)

        ctk.CTkLabel(popup,
            text="These tools must be installed before ScrcpyGUI can work properly.",
            font=ctk.CTkFont(FN,FS(10)), text_color=DIM, fg_color="transparent",
            wraplength=380).pack(pady=(12,4), padx=16, anchor="w")

        # Satu row per dependency
        dep_status = {}
        rows_frame = ctk.CTkFrame(popup, fg_color=BG)
        rows_frame.pack(fill="x", padx=16, pady=(4,0))

        for dep in missing:
            row = ctk.CTkFrame(rows_frame, fg_color=CARD, corner_radius=8,
                               border_width=1, border_color=BDR)
            row.pack(fill="x", pady=4)

            dot = ctk.CTkLabel(row, text="●", font=ctk.CTkFont(FN,FS(12),"bold"),
                               text_color=RED, fg_color="transparent", width=28)
            dot.pack(side="left", padx=(8,0))

            ctk.CTkLabel(row, text=dep, font=ctk.CTkFont(FNM,FS(10),"bold"),
                         text_color=TEXT, fg_color="transparent", width=80,
                         anchor="w").pack(side="left", padx=(4,0))

            ctk.CTkLabel(row, text=hints.get(dep,""), font=ctk.CTkFont(FNM,FS(9)),
                         text_color=DIM, fg_color="transparent",
                         anchor="w").pack(side="left", padx=8, fill="x", expand=True)

            dep_status[dep] = dot

        # Tombol bawah
        btn_row = ctk.CTkFrame(popup, fg_color=BG)
        btn_row.pack(fill="x", padx=16, pady=12)

        def _recheck():
            """Re-check tiap dep, update dot warna, unlock jika semua OK."""
            for dep, dot in dep_status.items():
                dot.configure(text_color=YEL)  # checking
            def _do():
                still_missing = []
                for dep in missing:
                    cmd = hints.get(dep,"").split()[-1:]  # extract package name only
                    try:
                        r = subprocess.run([dep,"--version"] if dep not in ["adb","pactl"] else [dep,"version" if dep=="adb" else "--version"],
                                           capture_output=True, timeout=5)
                        ok = r.returncode == 0
                    except FileNotFoundError: ok = False
                    except: ok = True
                    self.after(0, lambda d=dep, o=ok: dep_status[d].configure(
                        text_color=GRN if o else RED))
                    if not ok: still_missing.append(dep)
                self._missing_deps = set(still_missing)
                if not still_missing:
                    self.after(0, lambda: [
                        self.lbl_status.configure(text="● Ready", text_color=DIM, fg_color=CARD2),
                        btn_continue.configure(state="normal", fg_color=GRN, hover_color="#28a745"),
                        popup.grab_release()
                    ])
            threading.Thread(target=_do, daemon=True).start()

        ctk.CTkButton(btn_row, text="↺  Re-check", command=_recheck,
            height=34, fg_color=CARD2, hover_color=BDR, text_color=DIM,
            font=ctk.CTkFont(FN,FS(10),"bold"), border_width=1, border_color=BDR,
            corner_radius=8).pack(side="left", padx=(0,8))

        btn_continue = ctk.CTkButton(btn_row, text="✓  Continue Anyway",
            command=lambda: [setattr(self, "_missing_deps", set()), popup.grab_release(), popup.destroy()],
            height=34, fg_color=CARD2, hover_color=BDR, text_color=DIM,
            font=ctk.CTkFont(FN,FS(10)), border_width=1, border_color=BDR,
            corner_radius=8)
        btn_continue.pack(side="right")

    def _connect_wifi(self):
        host = self.V["tcpip_host"].get().strip()
        port = self.V["tcpip_port"].get().strip() or "5555"
        if not host:
            messagebox.showwarning("Missing IP", "Enter device IP address first!")
            return
        addr = f"{host}:{port}"
        self._log_tcpip(f"$ adb connect {addr}", "info")
        def _run():
            ok, message = connect_wifi(host, port)
            if ok:
                self._log_tcpip(f"✓ {message}", "ok")
                self._log_tcpip("→ Refresh device list in Mirror tab", "info")
                self.after(500, self._refresh_devices)
            else:
                self._log_tcpip(f"Failed: {message}", "error")
        threading.Thread(target=_run, daemon=True).start()

    def _disconnect_wifi(self):
        host = self.V["tcpip_host"].get().strip()
        port = self.V["tcpip_port"].get().strip() or "5555"
        self._log_tcpip(f"$ adb disconnect {host + ':' + port if host else ''}", "info")
        def _run():
            ok, message = disconnect_wifi(host, port)
            if ok:
                self._log_tcpip(f"✓ {message}", "ok")
                self._log_tcpip("→ Reconnect USB cable if needed", "info")
                self.after(500, self._refresh_devices)
            else:
                self._log_tcpip(f"Error: {message}", "error")
        threading.Thread(target=_run, daemon=True).start()

    # ── Misc ──────────────────────────────────────────────────────────────────
    def _rescale_ui(self):
        """Re-detect DPI dan tampilkan popup scale lagi."""
        self.cfg["ui_scale_asked"] = False
        save_config(self.cfg)
        self._check_hidpi_startup()

    def _switch_theme(self, name: str):
        if self.V["theme"].get() == name: return
        self.V["theme"].set(name)
        apply_palette(name)
        self._save(); self._rebuild_ui()

    def _rebuild_ui(self):
        current_theme = self.V["theme"].get()
        self._preview_active  = False   # stop any running preview
        self._monitor_running = False
        for win in ["float_win","monitor_win"]:
            try:
                w = getattr(self, win, None)
                if w and w.winfo_exists(): w.destroy()
            except: pass
        for w in self.winfo_children():
            try: w.destroy()
            except: pass
        apply_palette(current_theme)
        self.configure(fg_color=BG)
        self._build_ui(); self._load_config_no_theme()
        self._refresh_devices(); self._build_floating()
        self._build_monitor()
        self._monitor_running = self.V["show_monitor"].get()
        self.after(1000, self._poll_monitor)

    def _pick_folder(self):
        d = filedialog.askdirectory(initialdir=self.V["rec_path"].get())
        if d: self.V["rec_path"].set(d)

    def _save(self):
        self.cfg.update({
            "bitrate":self.V["bitrate"].get(),"max_fps":self.V["fps"].get(),
            "resolution":self.V["resolution"].get(),"codec":self.V["codec"].get(),"video_encoder":self.V["video_encoder"].get(),
            "rotation":self.V["rotation"].get(),"mode":self.V["mode"].get(),
            "record_path":self.V["rec_path"].get(),"record_format":self.V["rec_fmt"].get(),
            "no_audio":self.V["no_audio"].get(),"audio_output":self.V["audio_output"].get(),"fullscreen":self.V["fullscreen"].get(),
            "borderless":self.V["borderless"].get(),"always_on_top":self.V["always_top"].get(),
            "stay_awake":self.V["stay_awake"].get(),"turn_screen_off":self.V["screen_off"].get(),
            "no_control":self.V["view_only"].get(),"window_title":self.V["win_title"].get(),
            "live_platform":self.V["live_platform"].get(),"live_key":self.V["live_key"].get(),
            "live_bitrate":self.V["live_bitrate"].get(),"live_resolution":self.V["live_res"].get(),
            "live_fps":self.V["live_fps"].get(),"show_floating":self.V["show_floating"].get(),
            "tcpip_port":self.V["tcpip_port"].get(),"tcpip_host":self.V["tcpip_host"].get(),
            "live_custom_url":self.V["live_custom_url"].get(),"theme":self.V["theme"].get(),
            "show_monitor":self.V["show_monitor"].get(),
            "cmd_preview_visible":self.V["cmd_preview_visible"].get(),
            "log_visible":self.V["log_visible"].get(),
            "minimize_to_tray":self.V["minimize_to_tray"].get(),
            # 
            "preview_interval":self.V["preview_interval"].get(),
            "preview_auto_start":self.V["preview_auto_start"].get(),
            "ui_scale":self.cfg.get("ui_scale",1.0),
            "ui_scale_asked":self.cfg.get("ui_scale_asked",False),
        })
        save_config(self.cfg)
        self.lbl_statusbar.configure(text="✓ Saved")
        self.after(2000, lambda: self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN"))

    def _copy_cmd(self):
        teks = " ".join(self._build_cmd())
        self.clipboard_clear(); self.clipboard_append(teks)
        self.lbl_statusbar.configure(text="✓ Copied!")
        self.after(1500, lambda: self.lbl_statusbar.configure(text=f"© {datetime.now().year}  VEN"))

    def _reset_config(self):
        if messagebox.askyesno("Reset","Reset all settings to default?"):
            try: os.remove(CONFIG_FILE)
            except: pass
            self.lbl_statusbar.configure(text="Reset — restart to apply")

    def _on_close(self):
        if self.V["minimize_to_tray"].get():
            self.withdraw(); self._show_tray_toast(); return
        any_running = self.running or self.live_running or len(self.running_devs) > 0
        if any_running:
            if not messagebox.askyesno("Quit","Still running. Stop all and quit?"): return
            self._stop()
        else:
            if not messagebox.askyesno("Quit","Are you sure you want to quit ScrcpyGUI?"): return
        self._preview_active  = False
        self._monitor_running = False
        self._destroy_all_windows()
        self.destroy()

    def _show_tray_toast(self):
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True); toast.attributes("-topmost", True)
        toast.configure(fg_color=CARD)
        fr = ctk.CTkFrame(toast, fg_color=CARD, corner_radius=10, border_width=1, border_color=ACC)
        fr.pack(padx=2, pady=2)
        ctk.CTkLabel(fr, text="ScrcpyGUI minimized", font=ctk.CTkFont(FN,FS(10),"bold"),
                     text_color=ACC, fg_color="transparent", padx=14, pady=6).pack()
        ctk.CTkLabel(fr, text="Running in background", font=ctk.CTkFont(FN,FS(9)),
                     text_color=DIM, fg_color="transparent", padx=14, pady=4).pack()
        ctk.CTkButton(fr, text="Show Again",
                      command=lambda: [toast.destroy(), self.deiconify()],
                      width=100, height=28, fg_color=ACC, hover_color="#0060cc",
                      text_color="white", font=ctk.CTkFont(FN,FS(9)), corner_radius=6
                      ).pack(pady=(0,8))
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        toast.update_idletasks()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{sw-tw-16}+{sh-th-60}")
        toast.after(5000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _destroy_all_windows(self):
        for win in ["float_win","monitor_win"]:
            try:
                w = getattr(self, win, None)
                if w and w.winfo_exists(): w.destroy()
            except: pass

    # ── Floating widget ───────────────────────────────────────────────────────
    def _float_live_mode(self, aktif):
        fw = self.float_win
        if aktif:
            fw.attributes("-alpha", 0.0)
            fw.bind("<Enter>", lambda e: fw.attributes("-alpha", 0.92))
            fw.bind("<Leave>", lambda e: fw.attributes("-alpha", 0.0))
        else:
            fw.unbind("<Enter>"); fw.unbind("<Leave>"); fw.attributes("-alpha", 1.0)

    def _build_floating(self):
        self.float_win = ctk.CTkToplevel(self)
        fw = self.float_win
        fw.overrideredirect(True); fw.attributes("-topmost", True)
        fw.configure(fg_color=CARD)
        sw = self.winfo_screenwidth(); sh = self.winfo_screenheight()
        fw.geometry(f"154x44+{(sw-154)//2}+{sh-80}")
        row = tk.Frame(fw, bg=CARD); row.pack(fill="both", expand=True)
        drag = tk.Label(row, text="⠿", bg=CARD, fg=BDR, font=(FNM,11), cursor="fleur", padx=6)
        drag.pack(side="left", fill="y")
        drag.bind("<ButtonPress-1>", lambda e: setattr(self,"_dx",e.x) or setattr(self,"_dy",e.y))
        drag.bind("<B1-Motion>", lambda e: fw.geometry(
            f"+{fw.winfo_x()+e.x-self._dx}+{fw.winfo_y()+e.y-self._dy}"))
        tk.Frame(row, bg=BDR, width=1).pack(side="left", fill="y")
        self.float_btn_toggle = ctk.CTkButton(row, text="▶", command=self._toggle,
            width=52, height=44, fg_color=CARD, hover_color=CARD2,
            text_color=GRN, font=ctk.CTkFont(FNM,FS(16),"bold"), corner_radius=0)
        self.float_btn_toggle.pack(side="left")
        tk.Frame(row, bg=BDR, width=1).pack(side="left", fill="y")
        ctk.CTkButton(row, text="📷", command=self._screenshot,
            width=52, height=44, fg_color=CARD, hover_color=CARD2,
            text_color=YEL, font=ctk.CTkFont(FNM,FS(16)), corner_radius=0).pack(side="left")
        if not self.V["show_floating"].get(): fw.withdraw()

    def _screenshot(self):
        targets = list(self.running_devs)
        if not targets:
            dev = self.V["device"].get()
            if dev and "no devices" not in dev:
                targets = [dev.split()[0]]
        if not targets:
            messagebox.showwarning("No Device", "No device connected!")
            return
        folder = os.path.expanduser("~/Pictures/scrcpy-screenshots")
        os.makedirs(folder, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        results = {}
        lock = threading.Lock()
        remaining = [len(targets)]

        def _capture_one(serial):
            path = os.path.join(folder, f"ss_{serial}_{ts}.png")
            ok, message = capture_screenshot(serial, path)
            if ok:
                self._log(f"→ Screenshot saved: {message}")
                with lock:
                    results[serial] = message
            else:
                self._log(f"ERROR screenshot {serial}: {message}")
                with lock:
                    results[serial] = None
            with lock:
                remaining[0] -= 1
                if remaining[0] == 0:
                    self.after(0, lambda: self._flash_screenshot_multi(results))

        for serial in targets:
            threading.Thread(target=_capture_one, args=(serial,), daemon=True).start()

    def _flash_screenshot_multi(self, results: dict):
        ok = [s for s, p in results.items() if p]
        failed = [s for s, p in results.items() if not p]
        total  = len(results)
        try: fx = self.float_win.winfo_x(); fy = self.float_win.winfo_y()
        except: fx = self.winfo_screenwidth()//2; fy = self.winfo_screenheight() - 120
        toast = ctk.CTkToplevel(self)
        toast.overrideredirect(True); toast.attributes("-topmost", True)
        toast.configure(fg_color=CARD)
        fr = ctk.CTkFrame(toast, fg_color=CARD, corner_radius=10, border_width=1,
                          border_color=GRN if ok else RED)
        fr.pack(padx=2, pady=2)
        title = f"✓ {len(ok)}/{total} screenshot(s) saved" if ok else "✗ Screenshot failed"
        ctk.CTkLabel(fr, text=title, font=ctk.CTkFont(FN,FS(10),"bold"),
                     text_color=GRN if ok else RED,
                     fg_color="transparent", padx=14, pady=8).pack()
        for serial, path in results.items():
            color = DIM if path else RED
            label = os.path.basename(path) if path else f"{serial} — failed"
            ctk.CTkLabel(fr, text=label, font=ctk.CTkFont(FN,FS(8)),
                         text_color=color, fg_color="transparent", padx=14, pady=2).pack(anchor="w")
        toast.update_idletasks()
        tw, th = toast.winfo_width(), toast.winfo_height()
        toast.geometry(f"+{fx-max(0,tw-60)}+{fy-th-8}")
        self.after(3000, lambda: toast.destroy() if toast.winfo_exists() else None)


if __name__ == "__main__":
    App().mainloop()
