"""Floating Control Widget"""

from typing import Optional
import tkinter as tk
import customtkinter as ctk  # type: ignore
from core.adb_manager import CARD, BDR, GRN, YEL, FNM
from ui.ui_constants import FS


class FloatingWidget(ctk.CTkToplevel):
    """Floating control window for quick access to common functions."""

    def __init__(self, parent, on_toggle, on_screenshot, visible: bool = True):
        """
        Initialize floating widget.
        
        Args:
            parent: Parent window (App)
            on_toggle: Callback() for play/pause button
            on_screenshot: Callback() for screenshot button
            visible: Initial visibility state
        """
        super().__init__(parent)

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=CARD)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"154x44+{(sw-154)//2}+{sh-80}")

        # Internal drag state
        self._drag_x = 0
        self._drag_y = 0

        # Root frame
        self.root_frame = tk.Frame(self, bg=CARD)
        self.root_frame.pack(fill="both", expand=True)

        # Drag handle
        drag = tk.Label(
            self.root_frame,
            text="⠿",
            bg=CARD,
            fg=BDR,
            font=(FNM, 11),
            cursor="fleur",
            padx=6
        )
        drag.pack(side="left", fill="y")
        drag.bind("<ButtonPress-1>", self._on_drag_start)
        drag.bind("<B1-Motion>", self._on_drag_motion)

        # Separator
        tk.Frame(self.root_frame, bg=BDR, width=1).pack(side="left", fill="y")

        # Toggle button
        self.btn_toggle = ctk.CTkButton(
            self.root_frame,
            text="▶",
            command=on_toggle,
            width=52,
            height=44,
            fg_color=CARD,
            hover_color="#45475a",
            text_color=GRN,
            font=ctk.CTkFont(FNM, FS(16), "bold"),
            corner_radius=0
        )
        self.btn_toggle.pack(side="left")

        # Separator
        tk.Frame(self.root_frame, bg=BDR, width=1).pack(side="left", fill="y")

        # Screenshot button
        self.btn_screenshot = ctk.CTkButton(
            self.root_frame,
            text="📷",
            command=on_screenshot,
            width=52,
            height=44,
            fg_color=CARD,
            hover_color="#45475a",
            text_color=YEL,
            font=ctk.CTkFont(FNM, FS(16)),
            corner_radius=0
        )
        self.btn_screenshot.pack(side="left")

        if not visible:
            self.withdraw()

    def _on_drag_start(self, event):
        """Track initial drag position."""
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag_motion(self, event):
        """Update window position during drag."""
        new_x = self.winfo_x() + event.x - self._drag_x
        new_y = self.winfo_y() + event.y - self._drag_y
        self.geometry(f"+{new_x}+{new_y}")

    def set_toggle_text(self, text: str, color: Optional[str] = None):
        """Update toggle button text and optionally color."""
        self.btn_toggle.configure(text=text)
        if color:
            self.btn_toggle.configure(text_color=color)

    def show(self):
        """Display floating widget."""
        self.deiconify()

    def hide(self):
        """Hide floating widget."""
        self.withdraw()

    def set_visible(self, visible: bool):
        """Set visibility state."""
        if visible:
            self.show()
        else:
            self.hide()
