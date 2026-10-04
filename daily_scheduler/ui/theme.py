"""Shared theme / colour definitions for the scheduler UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


PALETTES = {
    "light": {
        "bg": "#f0f2f5",
        "card": "#ffffff",
        "card_alt": "#f7f9fc",
        "fg": "#1f2933",
        "muted": "#6b7280",
        "accent": "#2563eb",
        "active": "#2563eb",
        "completed": "#16a34a",
        "upcoming": "#9ca3af",
        "missed": "#dc2626",
        "skipped": "#f59e0b",
        "break_bg": "#ecfdf5",
        "alarm_bg": "#fee2e2",
        "progress": "#2563eb",
        "header_bg": "#1e3a8a",
        "header_fg": "#ffffff",
    },
    "dark": {
        "bg": "#111827",
        "card": "#1f2937",
        "card_alt": "#273244",
        "fg": "#e5e7eb",
        "muted": "#9ca3af",
        "accent": "#60a5fa",
        "active": "#60a5fa",
        "completed": "#34d399",
        "upcoming": "#6b7280",
        "missed": "#f87171",
        "skipped": "#fbbf24",
        "break_bg": "#064e3b",
        "alarm_bg": "#7f1d1d",
        "progress": "#60a5fa",
        "header_bg": "#0b1220",
        "header_fg": "#f9fafb",
    },
}


def status_color(status: str, theme: dict) -> str:
    return {
        "active": theme["active"],
        "completed": theme["completed"],
        "upcoming": theme["upcoming"],
        "missed": theme["missed"],
        "skipped": theme["skipped"],
    }.get(status, theme["muted"])


def apply_theme(root: tk.Tk, theme_name: str) -> dict:
    theme = PALETTES[theme_name]
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=theme["bg"])

    style.configure(".", background=theme["bg"], foreground=theme["fg"],
                    font=("Segoe UI", 10))
    style.configure("TFrame", background=theme["bg"])
    style.configure("Card.TFrame", background=theme["card"])
    style.configure("CardAlt.TFrame", background=theme["card_alt"])
    style.configure("Header.TFrame", background=theme["header_bg"])
    style.configure("TLabel", background=theme["bg"], foreground=theme["fg"])
    style.configure("Card.TLabel", background=theme["card"], foreground=theme["fg"])
    style.configure("CardAlt.TLabel", background=theme["card_alt"],
                    foreground=theme["fg"])
    style.configure("Header.TLabel", background=theme["header_bg"],
                    foreground=theme["header_fg"], font=("Segoe UI", 16, "bold"))
    style.configure("Title.TLabel", background=theme["bg"],
                    foreground=theme["fg"], font=("Segoe UI", 20, "bold"))
    style.configure("Big.TLabel", background=theme["card"],
                    foreground=theme["accent"], font=("Consolas", 34, "bold"))
    style.configure("Subject.TLabel", background=theme["card"],
                    foreground=theme["fg"], font=("Segoe UI", 18, "bold"))
    style.configure("Topic.TLabel", background=theme["card"],
                    foreground=theme["muted"], font=("Segoe UI", 12))
    style.configure("Muted.TLabel", background=theme["card"],
                    foreground=theme["muted"], font=("Segoe UI", 10))
    style.configure("MutedBg.TLabel", background=theme["bg"],
                    foreground=theme["muted"], font=("Segoe UI", 10))
    style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"))
    style.configure("Section.TLabel", background=theme["bg"],
                    foreground=theme["accent"], font=("Segoe UI", 13, "bold"))

    style.configure("TButton", font=("Segoe UI", 10))
    style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
    style.configure("Treeview", background=theme["card"],
                    foreground=theme["fg"], fieldbackground=theme["card"],
                    rowheight=26, font=("Segoe UI", 10))
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
    style.map("Treeview",
              background=[("selected", theme["accent"])],
              foreground=[("selected", "#ffffff")])

    style.configure("TEntry", fieldbackground=theme["card"],
                    background=theme["card"], foreground=theme["fg"])
    style.configure("TCombobox", fieldbackground=theme["card"],
                    background=theme["card"], foreground=theme["fg"])
    style.map("TCombobox",
              fieldbackground=[("readonly", theme["card"])],
              foreground=[("readonly", theme["fg"])])

    style.configure("Horizontal.TProgressbar",
                    background=theme["progress"],
                    troughcolor=theme["card_alt"],
                    bordercolor=theme["card_alt"],
                    lightcolor=theme["progress"],
                    darkcolor=theme["progress"])

    return theme