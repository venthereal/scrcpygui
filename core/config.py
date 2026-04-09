import json
import os

CONFIG_FILE = os.path.expanduser("~/.config/scrcpy-gui/settings.json")

DEFAULT_CONFIG = {
    "bitrate": "8M",
    "max_fps": "60",
    "resolution": "(default)",
    "codec": "h264",
    "rotation": "0",
    "mode": "Mirror Only",
    "record_path": os.path.expanduser("~/Videos/scrcpy"),
    "record_format": "mp4",
    "no_audio": False,
    "audio_output": False,
    "fullscreen": False,
    "borderless": False,
    "always_on_top": False,
    "stay_awake": True,
    "turn_screen_off": False,
    "no_control": False,
    "window_title": "scrcpy",
    "live_platform": "YouTube",
    "live_key": "",
    "live_bitrate": "3000k",
    "live_resolution": "1280x720",
    "live_fps": "30",
    "live_custom_url": "",
    "show_floating": True,
    "tcpip_port": "5555",
    "tcpip_host": "",
    "theme": "dark",
    "show_monitor": True,
    "cmd_preview_visible": False,
    "log_visible": True,
    "minimize_to_tray": False,
    "preview_interval": "2s",
    "preview_auto_start": True,
    "ui_scale": 1.0,
    "ui_scale_asked": False,
}


def load_config():
    config = DEFAULT_CONFIG.copy()
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
    except Exception:
        pass
    return config


def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as exc:
        print(f"save_config error: {exc}")
