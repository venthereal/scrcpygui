"""Stream Preview Canvas Widget"""

import tkinter as tk
import customtkinter as ctk  # type: ignore
from core.adb_manager import FN, FNM
from ui.ui_constants import FS

try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_OK = True
except ImportError:
    PIL_OK = False


class PreviewCanvas(ctk.CTkCanvas):
    """Canvas for displaying preview images (PIL or Tk fallback)."""

    def __init__(self, parent, width: int = 316, height: int = 178):
        """
        Initialize preview canvas.
        
        Args:
            parent: Parent widget
            width: Canvas width in pixels
            height: Canvas height in pixels
        """
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bg="#111111",
            border=0
        )
        self.width = width
        self.height = height
        self._image_ref = None  # Prevent GC on PhotoImage
        self._display_placeholder()

    def _display_placeholder(self):
        """Draw idle placeholder."""
        self.delete("all")
        W, H = self.width, self.height

        self.create_rectangle(0, 0, W, H, fill="#111111", outline="")

        # Grid lines
        for x in range(0, W, 32):
            self.create_line(x, 0, x, H, fill="#1a1a1a", width=1)
        for y in range(0, H, 32):
            self.create_line(0, y, W, y, fill="#1a1a1a", width=1)

        # Center message
        self.create_text(W // 2, H // 2 - 18, text="📱", font=(FN, 28), fill="#333333")
        self.create_text(W // 2, H // 2 + 18, text="No Preview",
                        font=(FNM, 10), fill="#444444")
        self.create_text(W // 2, H // 2 + 36, text="press Capture or start streaming",
                        font=(FN, 8), fill="#333333")

    def display_placeholder(self):
        """Show placeholder message."""
        self._display_placeholder()

    def display_message(self, msg: str, color: str = "#666666"):
        """Display centered message on canvas."""
        self.delete("all")
        W, H = self.width, self.height
        self.create_rectangle(0, 0, W, H, fill="#111111", outline="")
        self.create_text(W // 2, H // 2, text=msg, font=(FN, 10),
                        fill=color, justify="center")

    def display_image(self, image_path: str):
        """
        Display image from file path.
        
        Args:
            image_path: Path to image file
            
        Returns:
            True if successfully displayed, False otherwise
        """
        try:
            if not PIL_OK:
                self.display_message("Pillow not available", "#888888")
                return False

            from PIL import Image  # type: ignore

            img = Image.open(image_path)

            # Maintain aspect ratio
            img.thumbnail((self.width, self.height), Image.LANCZOS)  # type: ignore

            photo = ImageTk.PhotoImage(img)
            self._image_ref = photo  # Keep reference

            self.delete("all")
            self.create_image(
                self.width // 2,
                self.height // 2,
                image=photo
            )
            return True
        except Exception as e:
            self.display_message(f"Error: {str(e)[:30]}", "#ff6b6b")
            return False
