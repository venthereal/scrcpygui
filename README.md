# ScrcpyGUI

A simple graphical interface for [scrcpy](https://github.com/Genymobile/scrcpy) by Genymobile.  
Built with Python + CustomTkinter. Tested on **Linux Mint 22.3**.

> ⚠️ This project is not affiliated with or endorsed by the scrcpy project or Genymobile.

---

## Features

- 📱 Mirror & control Android device
- 🔴 Livestream directly to YouTube (no OBS needed)
- 📶 Wireless connection via TCP/IP (WiFi)
- 📷 Screenshot via ADB
- 🎙️ Game audio only or mixed with microphone
- 🪟 Floating widget for quick access
- 📋 ADB & ffmpeg log panel

---

## Requirements

```bash
sudo apt install scrcpy ffmpeg adb xdotool python3
pip install customtkinter --break-system-packages
```

---

## Usage

```bash
python3 scrcpy_gui.py
```

---

## Livestream Pipeline

```
Android → scrcpy → x11grab → ffmpeg → RTMP → YouTube
```

---

## Platform Support

| Platform | Status |
|----------|--------|
| Linux Mint / Ubuntu | ✅ Tested |
| Other Debian-based | ⚠️ Should work |
| Arch / Fedora | ❓ Untested |
| Windows / macOS | ❌ Not supported |

---

## Status

🚧 Beta — personal side project, updated when time allows.  
Bug reports and suggestions are welcome!

---

## Credits

- [scrcpy](https://github.com/Genymobile/scrcpy) by Genymobile — the core engine behind this GUI
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) — UI framework
- [ffmpeg](https://ffmpeg.org) — stream encoding

---

## License

MIT License — free to use, modify, and distribute.

---

*Made with curiosity and free time after work. 😄*
