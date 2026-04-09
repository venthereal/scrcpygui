"""Dependency Checker Dialog"""

import customtkinter as ctk  # type: ignore
from core.adb_manager import BG, CARD, CARD2, BDR, TEXT, DIM, GRN, RED, YEL, FN, FNM
from ui.ui_constants import FS


class DependencyCheckerDialog(ctk.CTkToplevel):
    """Popup dialog for displaying and checking dependencies."""

    def __init__(self, parent, title: str = "Dependencies", close_callback=None):
        """
        Initialize dependency dialog.
        
        Args:
            parent: Parent window
            title: Dialog title
            close_callback: Optional callback when dialog closes
        """
        super().__init__(parent)

        self.title(title)
        self.geometry("500x400")
        self.configure(fg_color=BG)
        self.close_callback = close_callback

        # Header frame
        header = ctk.CTkFrame(self, fg_color=CARD, corner_radius=0)
        header.pack(fill="x", side="top")

        ctk.CTkLabel(
            header,
            text=title,
            font=ctk.CTkFont(FN, FS(12), "bold"),
            text_color=TEXT,
            fg_color=CARD
        ).pack(side="left", padx=16, pady=12)

        # Content frame with scrollable area
        content = ctk.CTkFrame(self, fg_color=BG)
        content.pack(fill="both", expand=True, padx=16, pady=12)

        self.text_widget = ctk.CTkTextbox(
            content,
            fg_color=CARD,
            border_color=BDR,
            border_width=1,
            text_color=DIM,
            font=ctk.CTkFont(FNM, FS(9)),
            wrap="word"
        )
        self.text_widget.pack(fill="both", expand=True)
        self.text_widget.configure(state="disabled")

        # Button row
        btn_frame = ctk.CTkFrame(self, fg_color=BG)
        btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkButton(
            btn_frame,
            text="Close",
            command=self._on_close,
            width=100,
            height=32,
            fg_color=CARD2,
            hover_color=CARD,
            text_color=TEXT,
            font=ctk.CTkFont(FN, FS(10)),
            corner_radius=6
        ).pack(side="right")

        # Make dialog modal-ish
        self.grab_set()
        self.transient(parent)

    def set_content(self, text: str):
        """Update dialog content."""
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", text)
        self.text_widget.configure(state="disabled")

    def add_dependency(self, name: str, status: str, color: str = DIM):
        """Add a dependency status line."""
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", f"{name}: {status}\n", ("dep_" + status))
        self.text_widget.configure(state="disabled")

    def _on_close(self):
        """Handle dialog close."""
        if self.close_callback:
            self.close_callback()
        self.destroy()
