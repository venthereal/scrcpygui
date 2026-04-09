import os
import re
import subprocess
import time
from typing import Dict, List, Optional, Tuple


PALETTE_DARK = {
    "BG":"#1c1c1e","CARD":"#2c2c2e","CARD2":"#3a3a3c",
    "BDR":"#48484a","TEXT":"#ffffff","DIM":"#ebebf5",
}
PALETTE_LIGHT = {
    "BG":"#f2f2f7","CARD":"#ffffff","CARD2":"#e5e5ea",
    "BDR":"#c7c7cc","TEXT":"#000000","DIM":"#3a3a3c",
}

BG: str = PALETTE_DARK["BG"]
CARD: str = PALETTE_DARK["CARD"]
CARD2: str = PALETTE_DARK["CARD2"]
BDR: str = PALETTE_DARK["BDR"]
TEXT: str = PALETTE_DARK["TEXT"]
DIM: str = PALETTE_DARK["DIM"]

ACC: str = "#0a84ff"
RED: str = "#ff453a"
YEL: str = "#ffd60a"
GRN: str = "#30d158"
FN: str = "DejaVu Sans"
FNM: str = "DejaVu Sans Mono"

MODES: List[str] = ["Mirror Only", "Record", "Livestream"]
PLATFORM_RTMP: Dict[str, str] = {
    "YouTube": "rtmp://a.rtmp.youtube.com/live2/",
    "Custom":  "",
}

PRESETS = {
    "Performance": {
        "bitrate":"8M","max_fps":"60","resolution":"1080","codec":"h264",
        "borderless":True,"always_on_top":True,"stay_awake":True,
        "turn_screen_off":True,"fullscreen":False,"no_audio":False,"no_control":False,
    },
    "Balanced": {
        "bitrate":"4M","max_fps":"30","resolution":"720","codec":"h264",
        "borderless":True,"always_on_top":False,"stay_awake":True,
        "turn_screen_off":False,"fullscreen":False,"no_audio":False,"no_control":False,
    },
    "Saver": {
        "bitrate":"2M","max_fps":"24","resolution":"480","codec":"h264",
        "borderless":False,"always_on_top":False,"stay_awake":True,
        "turn_screen_off":True,"fullscreen":False,"no_audio":False,"no_control":False,
    },
}

# Type hint for COMPOSITOR_FIXES: Dict[str, Tuple[List[str], Dict[str, str], str, str]]
# Structure: (extra_args, env_vars, label, color)
COMPOSITOR_FIXES: Dict[str, Tuple[List[str], Dict[str, str], str, str]] = {
    "hyprland": (
        ["--render-driver=opengl"],
        {},
        "󰢹 Hyprland", "#a0e0ff",
    ),
    "sway": (
        ["--render-driver=opengl"],
        {},
        " Sway", "#a0e0ff",
    ),
    "gnome": (
        [],
        {"SDL_VIDEODRIVER": "x11"},
        " GNOME", "#f5a97f",
    ),
    "kde": (
        [],
        {"SDL_VIDEODRIVER": "x11"},
        " KDE", "#89b4fa",
    ),
    "niri": (
        ["--render-driver=opengl"],
        {},
        " niri", "#a6e3a1",
    ),
    "river": (
        ["--render-driver=opengl"],
        {},
        " river", "#a6e3a1",
    ),
}

REQUIRED_DEPS = [
    ("scrcpy",  ["scrcpy","--version"]),
    ("adb",     ["adb","version"]),
    ("ffmpeg",  ["ffmpeg","-version"]),
    ("xdotool", ["xdotool","--version"]),
    ("pactl",   ["pactl","--version"]),
]


def detect_audio_monitor() -> str:
    try:
        r = subprocess.run(["pactl","get-default-sink"], capture_output=True, text=True, timeout=5)
        sink = r.stdout.strip()
        if sink:
            return f"{sink}.monitor"
    except Exception:
        pass
    return "@DEFAULT_MONITOR@"


def detect_compositor() -> str:
    xdg = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session = os.environ.get("DESKTOP_SESSION", "").lower()
    wayland = os.environ.get("WAYLAND_DISPLAY", "")
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or "hyprland" in xdg:
        return "hyprland"
    if "sway" in xdg or "sway" in session:
        return "sway"
    if ("gnome" in xdg or "gnome" in session) and wayland:
        return "gnome"
    if ("kde" in xdg or "plasma" in xdg or "plasma" in session) and wayland:
        return "kde"
    if os.environ.get("NIRI_SOCKET") or "niri" in xdg:
        return "niri"
    try:
        r = subprocess.run(["pgrep", "-x", "river"], capture_output=True, timeout=2)
        if r.returncode == 0:
            return "river"
    except Exception:
        pass
    try:
        r = subprocess.run(["pgrep", "-x", "Hyprland"], capture_output=True, timeout=2)
        if r.returncode == 0:
            return "hyprland"
    except Exception:
        pass
    return ""


def is_hyprland() -> bool:
    return detect_compositor() == "hyprland"


def check_dependencies() -> List[str]:
    missing = []
    for name, cmd in REQUIRED_DEPS:
        try:
            subprocess.run(cmd, capture_output=True, timeout=5)
        except FileNotFoundError:
            missing.append(name)
        except Exception:
            pass
    return missing


def check_optional_dependencies() -> List[str]:
    """Check for optional dependencies by direct import (more reliable)."""
    missing = []
    try:
        from PIL import Image  # noqa
    except ImportError:
        missing.append("pillow")
    return missing


def scan_devices() -> Tuple[List[Tuple[str, str]], str]:
    devices: List[Tuple[str, str]] = []
    log_lines: List[str] = []
    try:
        r = subprocess.run(["adb","devices","-l"], capture_output=True, text=True, timeout=8)
        raw = r.stdout.strip()
        log_lines.append(raw)
        for ln in raw.splitlines()[1:]:
            ln = ln.strip()
            if not ln:
                continue
            parts = ln.split()
            if len(parts) < 2:
                continue
            serial, status = parts[0], parts[1]
            if status == "device":
                model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "device")
                icon = "📶" if "." in serial else "🔌"
                devices.append((serial, f"{serial}   [{model}] {icon}"))
            elif status == "unauthorized":
                devices.append((serial, f"{serial}   [UNAUTHORIZED ⚠]"))
            elif status == "offline":
                devices.append((serial, f"{serial}   [OFFLINE]"))
    except FileNotFoundError:
        log_lines.append("ERROR: adb not found")
    except subprocess.TimeoutExpired:
        log_lines.append("ERROR: adb timeout")
    except Exception as exc:
        log_lines.append(f"ERROR: {exc}")
    return devices, "\n".join(log_lines)


def enable_tcpip(port: str) -> Tuple[bool, str]:
    try:
        r = subprocess.run(["adb","tcpip", port], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return True, f"TCP/IP enabled on port {port}"
        return False, r.stderr.strip() or "Failed to enable TCP/IP"
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def detect_device_ip(serial: str) -> Tuple[bool, str]:
    try:
        r = subprocess.run(["adb","-s",serial,"shell","ip","addr","show","wlan0"],
                           capture_output=True, text=True, timeout=10)
        ip = None
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("inet ") and "127." not in line:
                ip = line.split()[1].split("/")[0]
                break
        if ip:
            return True, ip
        return False, "IP not found. Make sure WiFi is on!"
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def connect_wifi(host: str, port: str) -> Tuple[bool, str]:
    addr = f"{host}:{port}"
    try:
        r = subprocess.run(["adb","connect", addr], capture_output=True, text=True, timeout=15)
        out = r.stdout.strip()
        if "connected" in out.lower():
            return True, out
        return False, out or "Failed to connect"
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def disconnect_wifi(host: Optional[str] = None, port: str = "5555") -> Tuple[bool, str]:
    cmd = ["adb","disconnect"]
    if host:
        cmd.append(f"{host}:{port}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return True, r.stdout.strip()
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def capture_screenshot(serial: str, path: str, timeout: int = 10) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        r = subprocess.run(["adb","-s",serial,"exec-out","screencap","-p"],
                           capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            with open(path, "wb") as f:
                f.write(r.stdout)
            return True, path
        return False, r.stderr.decode(errors="replace").strip() or "Screenshot failed"
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def capture_device_preview(serial: str, output_path: str, timeout: int = 12) -> Tuple[bool, str]:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        r = subprocess.run(["adb","-s",serial,"exec-out","screencap","-p"],
                           capture_output=True, timeout=timeout)
        if r.returncode == 0 and r.stdout:
            with open(output_path, "wb") as f:
                f.write(r.stdout)
            return True, output_path
        return False, r.stderr.decode(errors="replace").strip() or "ADB screenshot failed"
    except FileNotFoundError:
        return False, "adb not found"
    except subprocess.TimeoutExpired:
        return False, "adb timeout"
    except Exception as exc:
        return False, str(exc)


def fetch_device_stats(serial: str, prev_net: Optional[Tuple[int, int, float]] = None) -> Tuple[Dict[str, str], Optional[Tuple[int, int, float]]]:
    stats: Dict[str, str] = {}
    current_net = prev_net
    try:
        r = subprocess.run(["adb","-s",serial,"shell","dumpsys","battery"],
                           capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines():
            if "level:" in line:
                stats["battery"] = f"{line.split(":",1)[1].strip()}%"
            elif "temperature:" in line:
                try:
                    t = int(line.split(":",1)[1].strip())
                    stats["temp"] = f"{t/10:.0f}°C"
                except Exception:
                    pass
    except Exception:
        stats["battery"] = "err"
    try:
        r = subprocess.run(["adb","-s",serial,"shell","cat","/proc/meminfo"],
                           capture_output=True, text=True, timeout=5)
        mem = {}
        for line in r.stdout.splitlines():
            if "MemTotal" in line or "MemAvailable" in line:
                k, v = line.split(":", 1)
                mem[k.strip()] = int(v.strip().split()[0])
        if "MemTotal" in mem and "MemAvailable" in mem:
            used = (mem["MemTotal"] - mem["MemAvailable"]) // 1024
            total = mem["MemTotal"] // 1024
            stats["ram"] = f"{used}/{total}M"
    except Exception:
        stats["ram"] = "err"
    try:
        def _read_cpu():
            r = subprocess.run(["adb","-s",serial,"shell","cat","/proc/stat"],
                               capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                if line.startswith("cpu "):
                    vals = list(map(int, line.split()[1:]))
                    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                    return idle, sum(vals)
            return None, None
        i1, t1 = _read_cpu()
        time.sleep(0.5)
        i2, t2 = _read_cpu()
        if i1 is not None and t1 is not None and i2 is not None and t2 is not None and (t2 - t1) > 0:
            stats["cpu"] = f"{100 * (1 - (i2 - i1) / (t2 - t1)):.0f}%"
    except Exception:
        stats["cpu"] = "err"
    try:
        r = subprocess.run(["adb","-s",serial,"shell","ping","-c","1","-W","2","8.8.8.8"],
                           capture_output=True, text=True, timeout=4)
        m = re.search(r'time=(\d+\.?\d*)', r.stdout)
        stats["ping"] = f"{m.group(1)}ms" if m else "timeout"
    except Exception:
        stats["ping"] = "err"
    try:
        r = subprocess.run(["adb","-s",serial,"shell","cat","/proc/net/dev"],
                           capture_output=True, text=True, timeout=5)
        rx_total = tx_total = 0
        for line in r.stdout.splitlines()[2:]:
            parts = line.split()
            if len(parts) < 10:
                continue
            iface = parts[0].rstrip(":")
            if iface == "lo":
                continue
            rx_total += int(parts[1]); tx_total += int(parts[9])
        now = time.time()
        if current_net:
            prev_rx, prev_tx, prev_t = current_net
            dt = max(now - prev_t, 0.1)
            rx_kb = (rx_total - prev_rx) / dt / 1024
            tx_kb = (tx_total - prev_tx) / dt / 1024
            def _fmt(kb):
                return f"{kb/1024:.1f}M" if kb >= 1024 else f"{kb:.0f}K"
            stats["net"] = f"↓{_fmt(rx_kb)} ↑{_fmt(tx_kb)}"
        else:
            stats["net"] = "measuring…"
        current_net = (rx_total, tx_total, now)
    except Exception:
        stats["net"] = "err"
    return stats, current_net
