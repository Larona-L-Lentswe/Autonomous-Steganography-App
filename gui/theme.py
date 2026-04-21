"""
gui/theme.py
─────────────────────────────────────────────────────────────
Colour palette, font constants, and reusable widget factories
shared across all GUI modules.
"""

import tkinter as tk

# ── Colours
BG_DARK      = "#0D0F14"
BG_PANEL     = "#161A23"
BG_HOVER     = "#1E2330"
ACCENT_EMBED = "#00C2FF"
ACCENT_EXTR  = "#00FF9C"
TEXT_PRIMARY = "#E8EAF0"
TEXT_MUTED   = "#5A6070"
TEXT_SUCCESS = "#00FF9C"
TEXT_ERROR   = "#FF4C6A"
BORDER       = "#252A36"

# ── Fonts
FONT_TITLE   = ("Courier New", 20, "bold")
FONT_LABEL   = ("Courier New", 10)
FONT_LABEL_B = ("Courier New", 10, "bold")
FONT_MONO    = ("Courier New", 9)
FONT_BTN     = ("Courier New", 11, "bold")
FONT_TOGGLE  = ("Courier New", 12, "bold")
FONT_STATUS  = ("Courier New", 9)


# ── Widget factories
def make_panel(parent, **kwargs):
    return tk.Frame(parent, bg=BG_PANEL, bd=0,
                    highlightthickness=1, highlightbackground=BORDER, **kwargs)


def make_label(parent, text, font=FONT_LABEL, color=TEXT_PRIMARY, **kwargs):
    return tk.Label(parent, text=text, font=font, fg=color,
                    bg=parent["bg"], **kwargs)


def make_entry(parent, textvariable, width=42):
    return tk.Entry(parent, textvariable=textvariable, width=width,
                    font=FONT_MONO, fg=TEXT_PRIMARY, bg="#0D0F14",
                    insertbackground=ACCENT_EMBED,
                    relief="flat", bd=0,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT_EMBED)


def make_button(parent, text, command, accent=ACCENT_EMBED, width=14):
    btn = tk.Button(parent, text=text, command=command,
                    font=FONT_BTN, fg=BG_DARK, bg=accent,
                    activebackground=accent, activeforeground=BG_DARK,
                    relief="flat", bd=0, cursor="hand2",
                    width=width, pady=6)
    def on_enter(_): btn.config(bg=TEXT_PRIMARY)
    def on_leave(_): btn.config(bg=accent)
    btn.bind("<Enter>", on_enter)
    btn.bind("<Leave>", on_leave)
    return btn


def make_browse_btn(parent, command):
    return tk.Button(parent, text="Browse", command=command,
                     font=FONT_MONO, fg=ACCENT_EMBED, bg=BG_PANEL,
                     activebackground=BG_HOVER, activeforeground=ACCENT_EMBED,
                     relief="flat", bd=0, cursor="hand2",
                     highlightthickness=1, highlightbackground=BORDER,
                     padx=8, pady=4)
