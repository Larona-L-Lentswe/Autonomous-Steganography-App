"""
main.py
─────────────────────────────────────────────────────────────
StegoVault — Entry Point
Comp 401 Final Project | Larona Lusindo Lentswe | ll23019090

Run with:
    python main.py
"""

import tkinter as tk

from gui.theme import (
    BG_DARK, BG_PANEL, BORDER,
    ACCENT_EMBED, ACCENT_EXTR, TEXT_PRIMARY, TEXT_MUTED,
    FONT_TITLE, FONT_TOGGLE, FONT_STATUS,
    make_label,
)
from gui.embed_frame   import EmbedFrame
from gui.extract_frame import ExtractFrame


# ─────────────────────────────────────────────
#  MODE TOGGLE
# ─────────────────────────────────────────────
class ModeToggle(tk.Frame):
    def __init__(self, parent, on_change, **kwargs):
        super().__init__(parent, bg=BG_DARK, **kwargs)
        self._mode      = "embed"
        self._on_change = on_change

        self._embed_btn = tk.Button(
            self, text="EMBED", font=FONT_TOGGLE,
            fg=BG_DARK, bg=ACCENT_EMBED,
            activebackground=ACCENT_EMBED, activeforeground=BG_DARK,
            relief="flat", bd=0, cursor="hand2", padx=28, pady=8,
            command=lambda: self._select("embed"))

        self._extr_btn = tk.Button(
            self, text="EXTRACT", font=FONT_TOGGLE,
            fg=TEXT_MUTED, bg=BG_PANEL,
            activebackground=BG_PANEL, activeforeground=TEXT_PRIMARY,
            relief="flat", bd=0, cursor="hand2", padx=28, pady=8,
            command=lambda: self._select("extract"))

        self._embed_btn.pack(side="left")
        tk.Frame(self, bg=BORDER, width=2).pack(side="left", fill="y")
        self._extr_btn.pack(side="left")

    def _select(self, mode):
        if mode == self._mode:
            return
        self._mode = mode
        if mode == "embed":
            self._embed_btn.config(fg=BG_DARK,    bg=ACCENT_EMBED)
            self._extr_btn.config( fg=TEXT_MUTED, bg=BG_PANEL)
        else:
            self._embed_btn.config(fg=TEXT_MUTED, bg=BG_PANEL)
            self._extr_btn.config( fg=BG_DARK,    bg=ACCENT_EXTR)
        self._on_change(mode)


# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class StegoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("StegoVault  //  Comp 401")
        self.configure(bg=BG_DARK)
        self.resizable(True, True)
        self.minsize(700, 580)
        self._build()
        self.update_idletasks()
        w, h = 800, 640
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        # ── Header
        header = tk.Frame(self, bg=BG_PANEL, height=54,
                          highlightthickness=1, highlightbackground=BORDER)
        header.pack(fill="x")
        header.pack_propagate(False)
        make_label(header, "  ◈ STEGO VAULT",
                   font=FONT_TITLE, color=TEXT_PRIMARY).pack(side="left", padx=(16, 0))
        make_label(header, "multi-carrier steganography  //  comp 401  ",
                   font=FONT_STATUS, color=TEXT_MUTED).pack(side="right")

        # ── Toggle bar
        toggle_bar = tk.Frame(self, bg=BG_DARK,
                              highlightthickness=1, highlightbackground=BORDER)
        toggle_bar.pack(fill="x")
        self._toggle = ModeToggle(toggle_bar, self._on_mode_change)
        self._toggle.pack(side="left", padx=20, pady=10)
        make_label(toggle_bar, "Select a mode above to begin  ›",
                   font=FONT_STATUS, color=TEXT_MUTED).pack(side="right", padx=20)

        # ── Content (swappable frames)
        self._content = tk.Frame(self, bg=BG_DARK)
        self._content.pack(fill="both", expand=True)

        self._embed_frame   = EmbedFrame(self._content, self)
        self._extract_frame = ExtractFrame(self._content, self)
        self._embed_frame.place(relwidth=1, relheight=1)
        self._active = "embed"

        # ── Footer
        footer = tk.Frame(self, bg=BG_PANEL, height=26,
                          highlightthickness=1, highlightbackground=BORDER)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        make_label(footer, "  Stegano · Pillow · Tkinter  //  Python 3   ",
                   font=FONT_STATUS, color=TEXT_MUTED).pack(side="right")
        make_label(footer, "  BIUST · Larona Lusindo Lentswe · ll23019090",
                   font=FONT_STATUS, color=TEXT_MUTED).pack(side="left")

    def _on_mode_change(self, mode):
        if mode == self._active:
            return
        self._active = mode
        if mode == "embed":
            self._extract_frame.place_forget()
            self._embed_frame.place(relwidth=1, relheight=1)
        else:
            self._embed_frame.place_forget()
            self._extract_frame.place(relwidth=1, relheight=1)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = StegoApp()
    app.mainloop()
