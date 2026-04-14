# ScrcpyGUI

A simple graphical interface for [scrcpy](https://github.com/Genymobile/scrcpy) by Genymobile.  
Built with Python + CustomTkinter. Tested on **Linux Mint 22.3 / Ubuntu 24.04**.

> ⚠️ This project is not affiliated with or endorsed by the scrcpy project or Genymobile.

---

## Preview

| | |
|---|---|
| ![](screenshots/1.png) | ![](screenshots/2.png) |
| ![](screenshots/3.png) | ![](screenshots/4.png) |
| ![](screenshots/5.png) | ![](screenshots/6.png) |
| ![](screenshots/7.png) | ![](screenshots/8.png) |

---

## Features

- 📱 Mirror & control Android device
- 🔴 Livestream directly to YouTube / Twitch / Facebook (no OBS needed)
- 📶 Wireless connection via TCP/IP (WiFi)
- 📷 Screenshot via ADB
- 🎙️ Game audio only or mixed with microphone
- 🪟 Floating widget for quick access
- 📋 ADB & ffmpeg log panel

---

## Platform Support

| Platform | Status |
|----------|--------|
| Linux Mint / Ubuntu 22.04+ | ✅ Tested |
| Debian 12+ | ✅ Should work |
| Arch Linux / Manjaro | ⚠️ Works with manual deps (see below) |
| Fedora / RHEL | ⚠️ Untested — package names differ |
| Windows / macOS | ❌ Not supported |

---

## Requirements

> This project is still in Beta. Using a virtual environment is strongly recommended.

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y scrcpy ffmpeg adb xdotool python3 python3-venv xvfb x11-xserver-utils pulseaudio-utils
```

### Arch Linux / Manjaro

```bash
sudo pacman -Sy scrcpy ffmpeg android-tools xdotool python xorg-xrandr xvfb-run pulseaudio
```

> **Note:** `xvfb` on Arch is provided by the `xorg-server-xvfb` package. If `pactl` is missing, install `libpulse`.

### Fedora

```bash
sudo dnf install scrcpy ffmpeg adb xdotool python3 xorg-x11-server-Xvfb xrandr pulseaudio-utils
```

> **Note:** Fedora may require enabling RPM Fusion for `ffmpeg` and `scrcpy`.

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/scrcpygui.git
cd scrcpygui
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install customtkinter pillow
```

### 4. Run

```bash
python3 main.py
```

### 5. Exit virtual environment

```bash
deactivate
```

---

## Editor Setup

This repository does not include `.vscode` settings by default. If you use VS Code, select the correct Python interpreter for the virtual environment via `Python: Select Interpreter`.

---

## Project Structure

```
scrcpygui/
├── core/           # Core modules (config, adb_manager)
├── ui/             # UI modules (tabs, widgets, dialogs)
│   ├── tabs/       # Tab builders (Mirror, Livestream, Settings, …)
│   ├── widgets/    # Reusable widget components
│   └── dialogs/    # Popup dialogs
├── main.py         # Application entry point
└── README.md
```

---

## Livestream Pipeline

```
Android → scrcpy → x11grab → ffmpeg → RTMP → YouTube / Twitch / Facebook
```

---

## Troubleshooting

**`scrcpy` not found** — make sure `adb devices` detects your device and USB debugging is enabled.

**Black screen on stream** — check that `Xvfb` is installed and your display variable is set correctly.

**`pactl` not found on Arch** — install `libpulse`: `sudo pacman -S libpulse`

**UI looks small on HiDPI** — open Settings → UI Scale → Re-detect, then apply the suggested scale.

**`ffmpeg` not found on Fedora** — enable RPM Fusion: https://rpmfusion.org/Configuration

---

## Credits

- [scrcpy](https://github.com/Genymobile/scrcpy) — core engine
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — UI framework
- [ffmpeg](https://ffmpeg.org) — stream encoding
- Android Debug Bridge (ADB) — device communication

---

## License

Licensed under the **GNU General Public License v3.0 (GPL-3.0)**.  
Free to use, modify, and distribute — keep source open and give credit.

---

*Made with curiosity and free time after work. 😄*
