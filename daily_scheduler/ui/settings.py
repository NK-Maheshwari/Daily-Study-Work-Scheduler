"""Settings screen - alarms, notifications, defaults, theme."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from database import Database
from ui.theme import apply_theme


class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, db: Database, on_change=None):
        super().__init__(parent)
        self.db = db
        self.on_change = on_change
        self.theme = parent.theme
        self.title("Settings")
        self.geometry("460x520")
        self.configure(bg=self.theme["bg"])
        self.transient(parent)

        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ttk.Label(card, text="Settings", style="Card.TLabel",
                  font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=12,
                                                      pady=(10, 8))

        s = self.db.get_settings()
        self.alarm = tk.BooleanVar(value=s.get("alarm_sound", "1") == "1")
        self.notifications = tk.BooleanVar(
            value=s.get("notifications", "1") == "1")
        self.auto_start = tk.BooleanVar(
            value=s.get("auto_start_next", "1") == "1")
        self.default_dur = tk.StringVar(
            value=s.get("default_task_duration", "60"))
        self.default_break = tk.StringVar(
            value=s.get("default_break_duration", "15"))
        self.theme_var = tk.StringVar(value=s.get("theme", "light"))
        self.tick = tk.StringVar(value=s.get("tick_interval_ms", "500"))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x", padx=12, pady=8)

        def check(text, var, row):
            ttk.Checkbutton(form, text=text, variable=var,
                            style="Card.TLabel").grid(row=row, column=0,
                                                      sticky="w", padx=12,
                                                      pady=6)

        check("Alarm sound", self.alarm, 0)
        check("Notifications", self.notifications, 1)
        check("Auto-start next task when time completes", self.auto_start, 2)

        ttk.Label(form, text="Default task duration (min):",
                  style="Card.TLabel").grid(row=3, column=0, sticky="w",
                                            padx=12, pady=6)
        ttk.Entry(form, textvariable=self.default_dur, width=6).grid(
            row=3, column=1, sticky="w", pady=6)

        ttk.Label(form, text="Default break duration (min):",
                  style="Card.TLabel").grid(row=4, column=0, sticky="w",
                                            padx=12, pady=6)
        ttk.Entry(form, textvariable=self.default_break, width=6).grid(
            row=4, column=1, sticky="w", pady=6)

        ttk.Label(form, text="Tick interval (ms, 250-1000):",
                  style="Card.TLabel").grid(row=5, column=0, sticky="w",
                                            padx=12, pady=6)
        ttk.Entry(form, textvariable=self.tick, width=6).grid(
            row=5, column=1, sticky="w", pady=6)

        ttk.Label(form, text="Theme:", style="Card.TLabel").grid(
            row=6, column=0, sticky="w", padx=12, pady=6)
        ttk.Combobox(form, textvariable=self.theme_var,
                     values=["light", "dark"], width=8,
                     state="readonly").grid(row=6, column=1, sticky="w",
                                            pady=6)

        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(pady=16)
        ttk.Button(btns, text="Save", command=self._save).pack(side="left",
                                                               padx=6)
        ttk.Button(btns, text="Close", command=self.destroy).pack(side="left",
                                                                  padx=6)
        self.grab_set()

    def _save(self) -> None:
        try:
            tick_ms = int(self.tick.get())
            tick_ms = max(250, min(tick_ms, 1000))
        except ValueError:
            tick_ms = 500
        self.db.set_setting("alarm_sound", "1" if self.alarm.get() else "0")
        self.db.set_setting("notifications",
                            "1" if self.notifications.get() else "0")
        self.db.set_setting("auto_start_next",
                            "1" if self.auto_start.get() else "0")
        self.db.set_setting("default_task_duration", self.default_dur.get())
        self.db.set_setting("default_break_duration", self.default_break.get())
        self.db.set_setting("theme", self.theme_var.get())
        self.db.set_setting("tick_interval_ms", str(tick_ms))
        if self.on_change:
            self.on_change()
        self.destroy()