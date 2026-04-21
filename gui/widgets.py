"""
gui/widgets.py
─────────────────────────────────────────────────────────────
Reusable custom widgets shared across GUI frames.
"""

import tkinter as tk
from gui.theme import BG_PANEL, BG_DARK, BORDER, TEXT_MUTED, FONT_STATUS


class ProgressBar(tk.Canvas):
    """Thin custom canvas progress bar."""
    def __init__(self, parent, accent, **kwargs):
        super().__init__(parent, height=6, bg=BG_PANEL,
                         bd=0, highlightthickness=0, **kwargs)
        self.accent = accent
        self._pct   = 0
        self.bind("<Configure>", lambda e: self._draw())

    def set(self, pct):
        self._pct = max(0, min(100, pct))
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        if w < 2:
            return
        self.create_rectangle(0, 0, w,   6, fill=BORDER,      outline="")
        fill_w = int(w * self._pct / 100)
        if fill_w > 0:
            self.create_rectangle(0, 0, fill_w, 6, fill=self.accent, outline="")


class LogBox(tk.Frame):
    """Scrollable dark-themed log output box."""
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=BG_PANEL, **kwargs)
        self._text = tk.Text(self, font=FONT_STATUS, fg=TEXT_MUTED,
                             bg=BG_DARK, relief="flat", bd=0,
                             state="disabled", wrap="word",
                             highlightthickness=0, height=6)
        scroll = tk.Scrollbar(self, command=self._text.yview,
                              bg=BG_PANEL, troughcolor=BG_PANEL,
                              relief="flat", bd=0)
        self._text.configure(yscrollcommand=scroll.set)
        self._text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=4)
        scroll.pack(side="right", fill="y")

    def log(self, msg, color=TEXT_MUTED):
        self._text.configure(state="normal")
        self._text.insert("end", f"  › {msg}\n")
        tag = f"tag_{self._text.index('end')}"
        self._text.tag_add(tag, "end - 2 lines linestart", "end - 1 lines")
        self._text.tag_config(tag, foreground=color)
        self._text.configure(state="disabled")
        self._text.see("end")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")
