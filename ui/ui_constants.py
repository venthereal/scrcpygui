"""UI Constants - only UI-specific scaling and styling functions.

All color palettes, fonts, presets, and modes are imported from core.adb_manager
to avoid duplication. This module contains only UI-specific constants.
"""

# ── UI Scale (will be set at startup) ────────────────────────────────────────
UI_SCALE: float = 1.0


def FS(size: int) -> int:
    """Scale font size according to DPI."""
    return max(7, round(size * UI_SCALE))


def set_ui_scale(scale: float):
    """Update global UI_SCALE value."""
    global UI_SCALE
    UI_SCALE = max(0.75, min(2.0, scale))


# ── Recording Settings ────────────────────────────────────────────────────────────
RECORD_FILTERS = [
    ("MP4 Video", "*.mp4"),
    ("MKV Video", "*.mkv"),
    ("All Files", "*.*"),
]

# ── TCP/IP Default Port ──────────────────────────────────────────────────────────
TCPIP_DEFAULT_PORT = 5555
