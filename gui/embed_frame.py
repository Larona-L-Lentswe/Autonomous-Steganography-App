"""
gui/embed_frame.py
─────────────────────────────────────────────────────────────
Embed Mode UI panel.
Wired to core.embed_engine.embed() via a background thread.
"""

import os
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

from gui.theme import (
    BG_DARK, BG_PANEL, BG_HOVER, BORDER,
    ACCENT_EMBED, TEXT_PRIMARY, TEXT_MUTED, TEXT_SUCCESS, TEXT_ERROR,
    FONT_LABEL, FONT_LABEL_B, FONT_MONO, FONT_BTN, FONT_STATUS,
    make_panel, make_label, make_entry, make_button, make_browse_btn,
)
from gui.widgets import ProgressBar, LogBox
from core.fragment_manager import fragment_sizes, estimate_fragments
from core.embed_engine import embed


class EmbedFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_DARK)
        self.app = app

        self._file_var    = tk.StringVar()
        self._carrier_var = tk.StringVar()
        self._out_var     = tk.StringVar()

        # Fragment size selector
        self._size_labels = list(fragment_sizes().keys())   # ["256 KB", "512 KB", …]
        self._size_map    = fragment_sizes()
        self._size_var    = tk.StringVar(value=self._size_labels[1])  # default 512 KB
        self._frag_count_var = tk.StringVar(value="—")

        self._file_var.trace_add("write", self._update_frag_estimate)
        self._size_var.trace_add("write",  self._update_frag_estimate)

        self._build()

    # ─────────────────────────────────────────
    #  Build
    # ─────────────────────────────────────────
    def _build(self):
        make_label(self, "  EMBED MODE", font=FONT_LABEL_B,
                   color=ACCENT_EMBED).pack(anchor="w", pady=(18, 8), padx=20)

        # ── File inputs panel
        panel = make_panel(self)
        panel.pack(fill="x", padx=20, pady=(0, 6))

        self._add_file_row(panel, "File to Hide",
                           self._file_var, self._browse_file, row=0)
        tk.Frame(panel, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=12)
        self._add_file_row(panel, "Carrier Images Folder",
                           self._carrier_var, self._browse_carrier, row=2)
        tk.Frame(panel, bg=BORDER, height=1).grid(
            row=3, column=0, columnspan=3, sticky="ew", padx=12)
        self._add_file_row(panel, "Output Folder",
                           self._out_var, self._browse_out, row=4)
        panel.columnconfigure(1, weight=1)

        # ── Fragment size panel
        frag_panel = make_panel(self)
        frag_panel.pack(fill="x", padx=20, pady=(0, 6))

        make_label(frag_panel, "  Fragment Size", font=FONT_LABEL_B,
                   color=TEXT_PRIMARY).grid(
            row=0, column=0, padx=(12, 6), pady=(10, 4), sticky="w")

        # Radio buttons for each size
        btn_row = tk.Frame(frag_panel, bg=BG_PANEL)
        btn_row.grid(row=0, column=1, padx=4, pady=(10, 4), sticky="w")

        for label in self._size_labels:
            rb = tk.Radiobutton(
                btn_row, text=label,
                variable=self._size_var, value=label,
                font=FONT_MONO,
                fg=TEXT_PRIMARY, bg=BG_PANEL,
                selectcolor=BG_DARK,
                activebackground=BG_PANEL, activeforeground=ACCENT_EMBED,
                indicatoron=True, relief="flat",
                cursor="hand2", padx=10,
            )
            rb.pack(side="left")

        # Fragment count estimate display
        est_frame = tk.Frame(frag_panel, bg=BG_PANEL)
        est_frame.grid(row=1, column=0, columnspan=3,
                       padx=12, pady=(0, 10), sticky="w")
        make_label(est_frame, "Estimated fragments:", font=FONT_STATUS,
                   color=TEXT_MUTED).pack(side="left")
        tk.Label(est_frame, textvariable=self._frag_count_var,
                 font=FONT_LABEL_B, fg=ACCENT_EMBED,
                 bg=BG_PANEL).pack(side="left", padx=(6, 0))

        frag_panel.columnconfigure(1, weight=1)

        # ── Progress + log
        self._prog = ProgressBar(self, accent=ACCENT_EMBED)
        self._prog.pack(fill="x", padx=20, pady=(4, 0))

        self._log = LogBox(self)
        self._log.pack(fill="x", padx=20, pady=(4, 0))

        # ── Action button
        self._btn = make_button(self, "▶  EMBED", self._run,
                                accent=ACCENT_EMBED, width=18)
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
    #  Fragment count estimate (live)
    # ─────────────────────────────────────────
    def _update_frag_estimate(self, *_):
        file_path   = self._file_var.get()
        size_label  = self._size_var.get()
        size_bytes  = self._size_map.get(size_label, 0)
        if not size_bytes:
            self._frag_count_var.set("—")
            return
        count = estimate_fragments(file_path, size_bytes)
        if count == 0:
            self._frag_count_var.set("—")
        else:
            self._frag_count_var.set(
                f"{count} fragment(s)  "
                f"(need ≥ {count} carrier image(s))"
            )

    # ─────────────────────────────────────────
    #  Browse
    # ─────────────────────────────────────────
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="Select File to Hide",
            filetypes=[("All files", "*.*")])
        if path:
            self._file_var.set(path)

    def _browse_carrier(self):
        path = filedialog.askdirectory(title="Select Carrier Images Folder")
        if path:
            self._carrier_var.set(path)

    def _browse_out(self):
        path = filedialog.askdirectory(title="Select Output Folder")
        if path:
            self._out_var.set(path)

    # ─────────────────────────────────────────
    #  Validation
    # ─────────────────────────────────────────
    def _validate(self):
        if not self._file_var.get() or not os.path.isfile(self._file_var.get()):
            messagebox.showerror("Missing Input", "Please select a valid file to hide.")
            return False
        if not self._carrier_var.get() or not os.path.isdir(self._carrier_var.get()):
            messagebox.showerror("Missing Input", "Please select a valid carrier images folder.")
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

        size_bytes = self._size_map[self._size_var.get()]
        q = queue.Queue()

        t = threading.Thread(
            target=embed,
            args=(self._file_var.get(), self._carrier_var.get(),
                  self._out_var.get(), size_bytes, q),
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
                    self._btn.config(state="normal", text="▶  EMBED")
                    return
                elif kind == "done":
                    self._btn.config(state="normal", text="▶  EMBED")
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._poll(q))
