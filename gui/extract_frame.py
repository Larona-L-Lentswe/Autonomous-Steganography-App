"""
gui/extract_frame.py
─────────────────────────────────────────────────────────────
Extract Mode UI panel.
Wired to core.extract_engine.extract() via a background thread.
"""

import os
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

from gui.theme import (
    BG_DARK, BG_PANEL, BORDER,
    ACCENT_EXTR, TEXT_PRIMARY, TEXT_MUTED, TEXT_SUCCESS, TEXT_ERROR,
    FONT_LABEL_B,
    make_panel, make_label, make_entry, make_button, make_browse_btn,
)
from gui.widgets import ProgressBar, LogBox
from core.extract_engine import extract


class ExtractFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_DARK)
        self.app = app
        self._stego_var = tk.StringVar()
        self._out_var   = tk.StringVar()
        self._build()

    # ─────────────────────────────────────────
    #  Build
    # ─────────────────────────────────────────
    def _build(self):
        make_label(self, "  EXTRACT MODE", font=FONT_LABEL_B,
                   color=ACCENT_EXTR).pack(anchor="w", pady=(18, 8), padx=20)

        panel = make_panel(self)
        panel.pack(fill="x", padx=20, pady=(0, 10))

        self._add_file_row(panel, "Stego Images Folder",
                           self._stego_var, self._browse_stego, row=0)
        tk.Frame(panel, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=12)
        self._add_file_row(panel, "Output Folder",
                           self._out_var, self._browse_out, row=2)
        panel.columnconfigure(1, weight=1)

        self._prog = ProgressBar(self, accent=ACCENT_EXTR)
        self._prog.pack(fill="x", padx=20, pady=(4, 0))

        self._log = LogBox(self)
        self._log.pack(fill="x", padx=20, pady=(4, 0))

        self._btn = make_button(self, "▶  EXTRACT", self._run,
                                accent=ACCENT_EXTR, width=18)
        self._btn.pack(anchor="e", padx=20, pady=12)

    # ─────────────────────────────────────────
    #  Widget helpers
    # ─────────────────────────────────────────
    def _add_file_row(self, parent, label, var, browse_cmd, row):
        tk.Label(parent, text=label, font=FONT_LABEL_B,
                 fg=TEXT_PRIMARY, bg=BG_PANEL,
                 width=22, anchor="w").grid(
            row=row, column=0, padx=(12, 6), pady=10, sticky="w")
        make_entry(parent, var).grid(
            row=row, column=1, padx=4, pady=10, sticky="ew")
        make_browse_btn(parent, browse_cmd).grid(
            row=row, column=2, padx=(4, 12), pady=10)

    # ─────────────────────────────────────────
    #  Browse
    # ─────────────────────────────────────────
    def _browse_stego(self):
        path = filedialog.askdirectory(title="Select Stego Images Folder")
        if path:
            self._stego_var.set(path)

    def _browse_out(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self._out_var.set(path)

    # ─────────────────────────────────────────
    #  Validation
    # ─────────────────────────────────────────
    def _validate(self):
        if not self._stego_var.get() or not os.path.isdir(self._stego_var.get()):
            messagebox.showerror("Missing Input", "Please select a valid stego images folder.")
            return False
        if not self._out_var.get():
            messagebox.showerror("Missing Input", "Please select an output folder.")
            return False
        return True

    # ─────────────────────────────────────────
    #  Run (background thread)
    # ─────────────────────────────────────────
    def _run(self):
        if not self._validate():
            return
        self._log.clear()
        self._prog.set(0)
        self._btn.config(state="disabled", text="  Working…")

        q = queue.Queue()
        t = threading.Thread(
            target=extract,
            args=(self._stego_var.get(), self._out_var.get(), q),
            daemon=True)
        t.start()
        self._poll(q)

    def _poll(self, q):
        try:
            while True:
                kind, pct, msg = q.get_nowait()
                if kind == "progress":
                    self._prog.set(pct)
                    color = TEXT_SUCCESS if pct == 100 else TEXT_MUTED
                    self._log.log(msg, color)
                elif kind == "error":
                    self._log.log(msg, TEXT_ERROR)
                    self._btn.config(state="normal", text="▶  EXTRACT")
                    return
                elif kind == "done":
                    self._btn.config(state="normal", text="▶  EXTRACT")
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._poll(q))
