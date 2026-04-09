# ScrcpyGUI Modularization Documentation

## Overview

ScrcpyGUI has been successfully modularized into a clean, maintainable structure. The codebase is now organized into logical modules with clear separation of concerns.

## Project Structure

```
scrcpygui-main/
├── main.py                           # Simple application entrypoint
├── README.md                         # Project documentation
├── LICENSE
├── .gitignore
├── .vscode/
│   └── settings.json                # VS Code configuration for Python analysis
│
├── core/                            # Core business logic
│   ├── __init__.py
│   ├── config.py                    # Configuration persistence (JSON)
│   └── adb_manager.py               # ADB operations, device management, dependencies
│
└── ui/                              # User interface module (CTkinter)
    ├── __init__.py                  # Package documentation
    ├── main_window.py               # Main App class (2400+ lines)
    ├── ui_constants.py              # Colors, fonts, themes, presets
    ├── ui_helpers.py                # DPI detection, palette management
    │
    ├── tabs/                        # Tab UI components
    │   ├── __init__.py
    │   └── base_tab.py              # BaseTab: common tab utilities
    │
    ├── widgets/                     # Reusable widget components
    │   ├── __init__.py
    │   ├── device_bar.py            # DeviceBar widget class
    │   ├── preview_canvas.py        # PreviewCanvas widget class
    │   └── floating_widget.py       # FloatingWidget window class
    │
    └── dialogs/                     # Dialog windows
        ├── __init__.py
        ├── dependency_dialog.py     # DependencyCheckerDialog class
        └── hidpi_dialog.py          # HiDPIDialog class
```

## Module Descriptions

### Core Module (`core/`)

#### `config.py`
- **Purpose**: Configuration persistence
- **Key Functions**:
  - `load_config()`: Load saved settings from JSON
  - `save_config(data)`: Persist settings to disk
- **Dependencies**: None (standalone)

#### `adb_manager.py`
- **Purpose**: ADB integration and device management
- **Key Functions**:
  - Device scanning and management
  - Dependency checking (scrcpy, adb, ffmpeg, etc.)
  - Device statistics (CPU, memory)
  - Audio monitor detection
- **Dependencies**: subprocess, json
- **Exports**: Colors, fonts, presets, RTMP platforms, compositor fixes

### UI Module (`ui/`)

#### `main_window.py` (Core UI - 2400+ lines)
- **Purpose**: Main application window and logic
- **Key Class**: `App(ctk.CTk)` - Main application root
- **Structure**:
  - Device management and scanning
  - Tab building (Mirror, Livestream, TCP/IP, Settings, Log)
  - Command building and preview
  - Process management for scrcpy instances
  - Device monitor and floating widget
- **Dependencies**: All ui submodules

#### `ui_constants.py` (Constants & Styles)
- **Purpose**: Centralized UI constants
- **Contents**:
  - Color palettes (dark and light)
  - Font definitions (`FN`, `FNM`)
  - UI colors (accent, red, yellow, green)
  - Modes, platforms, presets
  - Compositor fixes configuration
  - Helper function: `FS()` for font scaling

#### `ui_helpers.py` (Utility Functions)
- **Purpose**: System detection and styling utilities
- **Key Functions**:
  - `detect_system_dpi()`: Detect display DPI from xrandr/Tk
  - `apply_palette(name)`: Switch between light/dark themes
  - `configure_ui_scale(scale)`: Set global UI scale factor
- **Dependencies**: subprocess, Tk, ui_constants

#### `tabs/base_tab.py` (Base Tab Class)
- **Purpose**: Common functionality for all tabs
- **Key Class**: `BaseTab`
- **Methods**:
  - `section(parent, title)`: Create section headers with dividers
  - `combo_ctk(parent, values, var, width)`: Styled ComboBox creation

#### `widgets/device_bar.py` (Device Selection Widget)
- **Purpose**: Reusable device selection and refresh bar
- **Key Class**: `DeviceBar(ctk.CTkFrame)`
- **Key Methods**:
  - `set_devices(values)`: Update device list
  - `set_info(text)`: Update info label
- **Usage**: Encapsulates device combo, refresh button, and info display

#### `widgets/preview_canvas.py` (Preview Canvas)
- **Purpose**: Image preview display with PIL/Tk fallback
- **Key Class**: `PreviewCanvas(ctk.CTkCanvas)`
- **Key Methods**:
  - `display_image(path)`: Load and display image
  - `display_message(msg, color)`: Show text message
  - `display_placeholder()`: Show idle state
- **Features**: PIL support with Tk fallback, aspect ratio handling

#### `widgets/floating_widget.py` (Floating Control Window)
- **Purpose**: Draggable floating control panel
- **Key Class**: `FloatingWidget(ctk.CTkToplevel)`
- **Key Methods**:
  - `show()` / `hide()`: Visibility control
  - `set_visible(bool)`: Set visibility state
  - `set_toggle_text(text, color)`: Update button display
- **Features**: Drag handle, play/pause, screenshot buttons

#### `dialogs/dependency_dialog.py` (Dependency Dialog)
- **Purpose**: Display dependency status information
- **Key Class**: `DependencyCheckerDialog(ctk.CTkToplevel)`
- **Key Methods**:
  - `set_content(text)`: Update dialog content
  - `add_dependency(name, status, color)`: Add status line

#### `dialogs/hidpi_dialog.py` (HiDPI Dialog)
- **Purpose**: HiDPI scale detection and adjustment
- **Key Class**: `HiDPIDialog(ctk.CTkToplevel)`
- **Features**: DPI detection, interactive scale slider, apply/skip buttons

## Import Strategy

### For Application Entry
```python
from ui import App
app = App()
app.mainloop()
```

### For Internal UI Module Use
```python
from ui.ui_constants import FS, COLORS, PRESETS
from ui.ui_helpers import detect_system_dpi, apply_palette
from ui.widgets import DeviceBar, PreviewCanvas, FloatingWidget
from ui.dialogs import DependencyCheckerDialog, HiDPIDialog
```

## Key Design Principles

1. **Separation of Concerns**
   - Constants separated from logic
   - Utility functions in helpers
   - Widgets as independent classes
   - Dialogs as self-contained windows

2. **Reusability**
   - Widgets can be used in other projects
   - Dialogs are self-contained
   - Constants can be overridden for theming

3. **Maintainability**
   - Each file ~100-300 lines (except main_window.py)
   - Clear module purposes
   - Logical organization
   - Comprehensive docstrings

4. **IDE Support**
   - Type hints for better completion
   - Proper imports for Pylance
   - Configuration via .vscode/settings.json
   - `*.egg-info` and cache directories excluded

## File Size Summary

| File | Size | Purpose |
|------|------|---------|
| main_window.py | 2400+ | Main app & UI |
| adb_manager.py | 341 | ADB operations |
| config.py | ~100 | Config I/O |
| ui_constants.py | ~200 | Constants |
| ui_helpers.py | ~60 | Utilities |
| base_tab.py | ~70 | Tab base class |
| device_bar.py | ~80 | Device widget |
| preview_canvas.py | ~150 | Canvas widget |
| floating_widget.py | ~150 | Floating widget |
| dependency_dialog.py | ~100 | Dependency popup |
| hidpi_dialog.py | ~120 | HiDPI dialog |

## Future Modularization Opportunities

While the current structure is well-organized, the following could be further modularized in future iterations if needed:

1. **Tab extraction**: Move `_build_tab_*` methods to separate files in `tabs/`
2. **Command building**: Extract command building logic to `logic/command_builder.py`
3. **Device logic**: Extract device management to `logic/device_manager.py`
4. **Process management**: Extract process handling to `logic/process_manager.py`
5. **Preview system**: Extract preview logic to `widgets/preview_system.py`

However, the current structure provides a good balance between organization and complexity, and the main_window.py class is still cohesive and manageable.

## Testing

All modules compile successfully and imports work correctly:

```bash
# Test imports
python3 -c "from ui import App; print('✓ Import successful')"

# Test app instantiation
python3 -c "from ui import App; app = App(); print('✓ App created')"

# Run the application
python3 main.py
```

## Compliance

✓ All files compile without syntax errors  
✓ Type hints added for IDE support  
✓ Pylance errors resolved  
✓ Clean, logical structure  
✓ Well-documented modules  
✓ Follows Python best practices  
