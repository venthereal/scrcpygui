"""
ScrcpyGUI UI Module

Organized modular structure for better maintainability:

Directory Structure:
├── main.py                    # Application entrypoint
├── ui/                        # UI module (this package)
│   ├── __init__.py           # Package initialization
│   ├── main_window.py        # Main App class (CTkinter root window)
│   ├── ui_constants.py       # Colors, fonts, themes, presets, constants
│   ├── ui_helpers.py         # Utility functions (DPI detection, palettes)
│   │
│   ├── tabs/                 # Tab UI building logic
│   │   ├── __init__.py
│   │   └── base_tab.py       # BaseTab class with common utilities
│   │
│   ├── widgets/              # Reusable widget components
│   │   ├── __init__.py
│   │   ├── device_bar.py     # Device selection bar
│   │   ├── preview_canvas.py # Image preview canvas
│   │   └── floating_widget.py # Floating control window
│   │
│   └── dialogs/              # Dialog windows
│       ├── __init__.py
│       ├── dependency_dialog.py # Dependency checker popup
│       └── hidpi_dialog.py      # HiDPI scale adjustment dialog
│
├── core/                      # Core logic module
│   ├── config.py
│   └── adb_manager.py
└── README.md
"""

from ui.main_window import App

__all__ = ["App"]

