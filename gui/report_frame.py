"""
gui/report_frame.py
─────────────────────────────────────────────────────────────
Steganalysis Report Frame — third mode in the toggle bar.
Reads a manifest.json + original carrier folder, runs all
metrics via report_engine, then opens a Matplotlib dashboard
window with bar charts and a statistics table.
"""

import os
import threading
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from gui.theme import (
    BG_DARK, BG_PANEL, BORDER,
    ACCENT_EMBED, ACCENT_EXTR, TEXT_PRIMARY, TEXT_MUTED,
    TEXT_SUCCESS, TEXT_ERROR,
    FONT_LABEL_B, FONT_STATUS, FONT_MONO,
    make_panel, make_label, make_button, make_browse_btn,
)
from gui.widgets import ProgressBar, LogBox
from core.report_engine import generate_report

# ── Matplotlib dark theme colours matching the app palette
MPL_BG      = "#0D0F14"
MPL_PANEL   = "#161A23"
MPL_BORDER  = "#252A36"
MPL_CYAN    = "#00C2FF"
MPL_GREEN   = "#00FF9C"
MPL_RED     = "#FF4C6A"
MPL_ORANGE  = "#FF9C00"
MPL_TEXT    = "#E8EAF0"
MPL_MUTED   = "#5A6070"

VERDICT_COLORS = {
    "green":  MPL_GREEN,
    "cyan":   MPL_CYAN,
    "orange": MPL_ORANGE,
    "red":    MPL_RED,
}


class ReportFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG_DARK)
        self.app = app
        self._manifest_var = tk.StringVar()
        self._carrier_var  = tk.StringVar()
        self._report_data  = None
        self._build()

    # ─────────────────────────────────────────
    #  Build input panel
    # ─────────────────────────────────────────
    def _build(self):
        make_label(self, "  REPORT MODE", font=FONT_LABEL_B,
                   color=MPL_ORANGE).pack(anchor="w", pady=(18, 8), padx=20)

        make_label(self,
            "  Select a manifest.json and the original carrier images folder "
            "to generate a full steganalysis report.",
            font=FONT_STATUS, color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(0, 8))

        # ── Input panel
        panel = make_panel(self)
        panel.pack(fill="x", padx=20, pady=(0, 8))

        self._add_row(panel, "manifest.json",
                      self._manifest_var, self._browse_manifest, row=0,
                      is_file=True)
        tk.Frame(panel, bg=BORDER, height=1).grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=12)
        self._add_row(panel, "Original Carriers Folder",
                      self._carrier_var, self._browse_carrier, row=2,
                      is_file=False)
        panel.columnconfigure(1, weight=1)

        # ── Progress + log
        self._prog = ProgressBar(self, accent=MPL_ORANGE)
        self._prog.pack(fill="x", padx=20, pady=(4, 0))

        self._log = LogBox(self)
        self._log.pack(fill="x", padx=20, pady=(4, 0))

        # ── Action button
        self._btn = make_button(self, "▶  GENERATE REPORT", self._run,
                                accent=MPL_ORANGE, width=22)
        self._btn.pack(anchor="e", padx=20, pady=12)

    def _add_row(self, parent, label, var, browse_cmd, row, is_file):
        tk.Label(parent, text=label, font=FONT_LABEL_B,
                 fg=TEXT_PRIMARY, bg=BG_PANEL,
                 width=24, anchor="w").grid(
            row=row, column=0, padx=(12, 6), pady=10, sticky="w")
        tk.Entry(parent, textvariable=var, width=42,
                 font=FONT_MONO, fg=TEXT_PRIMARY, bg="#0D0F14",
                 insertbackground=MPL_ORANGE,
                 relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=MPL_ORANGE).grid(
            row=row, column=1, padx=4, pady=10, sticky="ew")
        make_browse_btn(parent, browse_cmd).grid(
            row=row, column=2, padx=(4, 12), pady=10)

    # ─────────────────────────────────────────
    #  Browse
    # ─────────────────────────────────────────
    def _browse_manifest(self):
        path = filedialog.askopenfilename(
            title="Select manifest.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")])
        if path:
            self._manifest_var.set(path)

    def _browse_carrier(self):
        path = filedialog.askdirectory(title="Select Original Carriers Folder")
        if path:
            self._carrier_var.set(path)

    # ─────────────────────────────────────────
    #  Validation
    # ─────────────────────────────────────────
    def _validate(self):
        if not self._manifest_var.get() or \
                not os.path.isfile(self._manifest_var.get()):
            messagebox.showerror("Missing Input",
                                 "Please select a valid manifest.json file.")
            return False
        if not self._carrier_var.get() or \
                not os.path.isdir(self._carrier_var.get()):
            messagebox.showerror("Missing Input",
                                 "Please select the original carriers folder.")
            return False
        return True

    # ─────────────────────────────────────────
    #  Run report engine in background thread
    # ─────────────────────────────────────────
    def _run(self):
        if not self._validate():
            return
        self._log.clear()
        self._prog.set(0)
        self._btn.config(state="disabled", text="  Analysing…")
        self._report_data = None

        q = queue.Queue()
        t = threading.Thread(
            target=self._worker,
            args=(self._manifest_var.get(),
                  self._carrier_var.get(), q),
            daemon=True)
        t.start()
        self._poll(q)

    def _worker(self, manifest_path, carrier_folder, q):
        report = generate_report(manifest_path, carrier_folder, q)
        q.put(("report", report, None))

    def _poll(self, q):
        try:
            while True:
                item = q.get_nowait()
                kind, data, msg = item

                if kind == "progress":
                    self._prog.set(data)
                    color = TEXT_SUCCESS if data == 100 else TEXT_MUTED
                    self._log.log(msg, color)

                elif kind == "error":
                    self._log.log(msg, TEXT_ERROR)
                    self._btn.config(state="normal",
                                     text="▶  GENERATE REPORT")
                    return

                elif kind == "report":
                    self._report_data = data
                    self._btn.config(state="normal",
                                     text="▶  GENERATE REPORT")
                    if data and not data.get("error"):
                        self._open_dashboard(data)
                    return

                elif kind == "done":
                    pass

        except queue.Empty:
            pass
        self.after(100, lambda: self._poll(q))

    # ─────────────────────────────────────────
    #  Dashboard window
    # ─────────────────────────────────────────
    def _open_dashboard(self, report: dict):
        """Open a Toplevel window with matplotlib charts."""
        win = tk.Toplevel(self)
        win.title("StegoVault — Steganalysis Report")
        win.configure(bg=MPL_BG)
        win.geometry("1000x700")
        win.minsize(800, 600)

        frags   = report["per_fragment"]
        summary = report["summary"]
        valid   = [f for f in frags if f["psnr"] is not None]
        n       = len(valid)

        if n == 0:
            tk.Label(win, text="No valid fragment data to display.",
                     bg=MPL_BG, fg=MPL_RED,
                     font=("Courier New", 14)).pack(expand=True)
            return

        indices = [f["fragment_index"] for f in valid]

        # ── Header bar
        hdr = tk.Frame(win, bg=MPL_PANEL, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr,
                 text=f"  ◈ STEGANALYSIS REPORT  —  {report['original_name']}",
                 font=("Courier New", 14, "bold"),
                 fg=TEXT_PRIMARY, bg=MPL_PANEL).pack(side="left", padx=12)
        verdict = summary.get("verdict", "NO DATA")
        vcol    = VERDICT_COLORS.get(summary.get("verdict_color", "red"), MPL_RED)
        tk.Label(hdr, text=f"  {verdict}  ",
                 font=("Courier New", 11, "bold"),
                 fg=MPL_BG, bg=vcol).pack(side="right", padx=12, pady=8)

        # ── Matplotlib figure
        fig = plt.Figure(figsize=(12, 7), facecolor=MPL_BG)
        gs  = gridspec.GridSpec(
            2, 2,
            figure=fig,
            hspace=0.45, wspace=0.38,
            left=0.08, right=0.97,
            top=0.90, bottom=0.12,
        )

        # ── Shared x-axis setup
        x      = np.arange(n)
        width  = 0.55

        def _style_ax(ax, title, ylabel):
            ax.set_facecolor(MPL_PANEL)
            ax.set_title(title, color=TEXT_PRIMARY,
                         fontsize=10, fontweight="bold",
                         fontfamily="monospace", pad=8)
            ax.set_ylabel(ylabel, color=MPL_MUTED,
                          fontsize=8, fontfamily="monospace")
            ax.set_xlabel("Fragment Index", color=MPL_MUTED,
                          fontsize=8, fontfamily="monospace")
            ax.tick_params(colors=MPL_MUTED, labelsize=7)
            ax.set_xticks(x)
            ax.set_xticklabels([str(i) for i in indices], fontsize=8)
            for spine in ax.spines.values():
                spine.set_edgecolor(MPL_BORDER)
            ax.grid(axis="y", color=MPL_BORDER,
                    linestyle="--", linewidth=0.5, alpha=0.7)

        def _bar(ax, values, color, label):
            bars = ax.bar(x, values, width, color=color,
                          alpha=0.85, label=label)
            for bar, val in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_height() * 1.01,
                        f"{val:.3f}",
                        ha="center", va="bottom",
                        color=color, fontsize=6.5,
                        fontfamily="monospace")
            return bars

        # ── 1. PSNR bar chart
        ax1 = fig.add_subplot(gs[0, 0])
        psnr_vals = [f["psnr"] for f in valid]
        _bar(ax1, psnr_vals, MPL_CYAN, "PSNR")
        ax1.axhline(y=45, color=MPL_GREEN, linestyle="--",
                    linewidth=0.8, label="Good threshold (45 dB)")
        ax1.axhline(y=35, color=MPL_RED, linestyle=":",
                    linewidth=0.8, label="Poor threshold (35 dB)")
        _style_ax(ax1, "PSNR per Fragment", "PSNR (dB)")
        ax1.legend(fontsize=7, labelcolor=MPL_MUTED,
                   facecolor=MPL_PANEL, edgecolor=MPL_BORDER)

        # ── 2. SSIM bar chart
        ax2 = fig.add_subplot(gs[0, 1])
        ssim_vals = [f["ssim"] for f in valid]
        _bar(ax2, ssim_vals, MPL_GREEN, "SSIM")
        ax2.axhline(y=0.999, color=MPL_CYAN, linestyle="--",
                    linewidth=0.8, label="Excellent (0.999)")
        ax2.axhline(y=0.995, color=MPL_RED, linestyle=":",
                    linewidth=0.8, label="Good (0.995)")
        ax2.set_ylim(
            max(0, min(ssim_vals) - 0.005),
            min(1.005, max(ssim_vals) + 0.005)
        )
        _style_ax(ax2, "SSIM per Fragment", "SSIM Score")
        ax2.legend(fontsize=7, labelcolor=MPL_MUTED,
                   facecolor=MPL_PANEL, edgecolor=MPL_BORDER)

        # ── 3. Summary statistics table (bottom left)
        ax3 = fig.add_subplot(gs[1, 0])
        ax3.set_facecolor(MPL_BG)
        ax3.axis("off")

        col_labels = ["Metric", "Average", "Min", "Max", "Threshold", "Status"]
        metrics_data = [
            [
                "PSNR (dB)",
                f"{summary['avg_psnr']:.4f}",
                f"{min(psnr_vals):.4f}",
                f"{max(psnr_vals):.4f}",
                "≥ 45 dB (Good)",
                "✓ PASS" if summary["avg_psnr"] >= 45 else "✗ FAIL",
            ],
            [
                "SSIM",
                f"{summary['avg_ssim']:.6f}",
                f"{min(ssim_vals):.6f}",
                f"{max(ssim_vals):.6f}",
                "≥ 0.995 (Good)",
                "✓ PASS" if summary["avg_ssim"] >= 0.995 else "✗ FAIL",
            ],
        ]

        tbl = ax3.table(
            cellText=metrics_data,
            colLabels=col_labels,
            cellLoc="center",
            loc="center",
            bbox=[0, 0, 1, 1],
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(9)

        # Style header
        for col in range(len(col_labels)):
            cell = tbl[0, col]
            cell.set_facecolor(MPL_PANEL)
            cell.set_text_props(color=MPL_CYAN,
                                fontfamily="monospace",
                                fontweight="bold")
            cell.set_edgecolor(MPL_BORDER)

        # Style data rows
        row_colors = [MPL_CYAN, MPL_GREEN]
        for row_i, row_data in enumerate(metrics_data):
            for col_i in range(len(col_labels)):
                cell = tbl[row_i + 1, col_i]
                cell.set_facecolor(MPL_PANEL if row_i % 2 == 0 else "#1A1F2E")
                cell.set_edgecolor(MPL_BORDER)
                status_text = row_data[-1]
                if col_i == 0:
                    cell.set_text_props(
                        color=row_colors[row_i],
                        fontfamily="monospace",
                        fontweight="bold"
                    )
                elif col_i == len(col_labels) - 1:
                    color = MPL_GREEN if "PASS" in status_text else MPL_RED
                    cell.set_text_props(
                        color=color,
                        fontfamily="monospace",
                        fontweight="bold"
                    )
                else:
                    cell.set_text_props(
                        color=TEXT_PRIMARY,
                        fontfamily="monospace"
                    )

        ax3.set_title(
            f"Summary Statistics  —  {n} fragment(s)  |  "
            f"Method: {report.get('pairing_method', 'N/A')}  |  "
            f"File: {report['original_name']}",
            color=TEXT_PRIMARY, fontsize=9,
            fontweight="bold", fontfamily="monospace",
            pad=10,
        )

        # ── 4. Information panel (bottom right)
        ax4 = fig.add_subplot(gs[1, 1])
        ax4.set_facecolor(MPL_PANEL)
        ax4.axis("off")

        info_text = (
            f"Report Information\n"
            f"{'─' * 40}\n\n"
            f"Original File: {report['original_name']}\n"
            f"SHA-256 Hash: {report['original_hash'][:32]}...\n"
            f"Total Fragments: {report['total_fragments']}\n"
            f"Valid Fragments: {summary.get('fragments_ok', 0)}\n"
            f"Failed Fragments: {summary.get('fragments_err', 0)}\n\n"
            f"Quality Verdict: {verdict}\n\n"
            f"PSNR indicates the peak signal-to-noise ratio,\n"
            f"measuring the quality between original and\n"
            f"stego images. Higher PSNR = better quality.\n\n"
            f"SSIM measures structural similarity between\n"
            f"images, with 1.0 being identical."
        )

        ax4.text(0.05, 0.95, info_text,
                 transform=ax4.transAxes,
                 fontsize=9, verticalalignment='top',
                 color=TEXT_PRIMARY, fontfamily="monospace",
                 linespacing=1.5)

        # ── Embed figure in Toplevel
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True, padx=8, pady=8)

        # ── Footer
        footer = tk.Frame(win, bg=MPL_PANEL, height=26)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        tk.Label(footer,
                 text=f"  SHA-256: {report['original_hash']}  ",
                 font=("Courier New", 8), fg=TEXT_MUTED,
                 bg=MPL_PANEL).pack(side="left")
        tk.Label(footer,
                 text=f"  Fragments OK: {summary.get('fragments_ok', 0)}  "
                      f"Errors: {summary.get('fragments_err', 0)}  ",
                 font=("Courier New", 8), fg=TEXT_MUTED,
                 bg=MPL_PANEL).pack(side="right")