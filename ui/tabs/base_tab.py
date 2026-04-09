"""Base Tab class - common functionality for all tabs."""

import customtkinter as ctk  # type: ignore
from core.adb_manager import BG, CARD, CARD2, BDR, TEXT, DIM, FN, FNM, ACC
from ui.ui_constants import FS


class BaseTab:
    """Base class providing common tab UI building utilities."""

    def __init__(self, app):
        """Initialize with reference to parent App instance."""
        self.app = app

    def section(self, parent, title: str) -> ctk.CTkFrame:
        """
        Create a section header with a dividing line.
        
        Args:
            parent: Parent widget
            title: Section title text
            
        Returns:
            CTkFrame for the section content
        """
        frame = ctk.CTkFrame(parent, fg_color=BG)
        frame.pack(fill="x", pady=(12, 4))
        lbl = ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(FN, FS(9), "bold"),
            text_color=DIM,
            fg_color=BG
        )
        lbl.pack(anchor="w", padx=4, pady=2)
        
        div = ctk.CTkFrame(frame, fg_color=BDR, height=1, corner_radius=0)
        div.pack(fill="x", pady=(4, 0))

        return frame

    def combo_ctk(self, parent, values: list, var, width: int = 120) -> ctk.CTkComboBox:
        """
        Create a styled CTkComboBox.
        
        Args:
            parent: Parent widget
            values: List of combo values
            var: StringVar for value binding
            width: Widget width
            
        Returns:
            CTkComboBox widget
        """
        return ctk.CTkComboBox(
            parent,
            values=values,
            variable=var,
            width=width,
            font=ctk.CTkFont(FNM, FS(10)),
            fg_color=CARD,
            border_color=BDR,
            button_color=ACC,
            dropdown_fg_color=CARD,
            dropdown_text_color=TEXT,
            text_color=TEXT,
            state="readonly"
        )
