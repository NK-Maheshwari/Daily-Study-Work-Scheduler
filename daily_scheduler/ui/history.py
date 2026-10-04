"""History screen - review past days' completion statistics."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Optional

from database import Database
from models import format_minutes_short
from ui.theme import apply_theme


class HistoryWindow(tk.Toplevel):
    def __init__(self, parent, db: Database):
        super().__init__(parent)
        self.db = db
        self.theme = parent.theme
        self.title("History")
        self.geometry("720x560")
        self.configure(bg=self.theme["bg"])
        self.transient(parent)

        ttk.Label(self, text="DAILY HISTORY", style="Section.TLabel").pack(
            anchor="w", padx=14, pady=(12, 4))

        cols = ("date", "planned", "completed", "tasks", "missed", "pct")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (120, 90, 100, 80, 70, 70)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=14, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        detail = ttk.LabelFrame(self, text="Details")
        detail.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.detail_text = tk.Text(detail, height=10, wrap="word",
                                   bg=self.theme["card"],
                                   fg=self.theme["fg"],
                                   font=("Segoe UI", 10))
        self.detail_text.pack(fill="both", expand=True, padx=8, pady=8)

        self._load()
        self.grab_set()

    def _load(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for s in self.db.get_history(90):
            self.tree.insert("", "end", values=(
                s.date,
                format_minutes_short(s.planned_minutes),
                format_minutes_short(s.completed_minutes),
                f"{s.tasks_completed}/{s.tasks_total}",
                s.tasks_missed,
                f"{int(s.completion_pct)}%",
            ))

    def _on_select(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if not values:
            return
        day = values[0]
        s = self.db.get_summary(day)
        self.detail_text.delete("1.0", "end")
        if not s:
            return
        lines = [
            f"Date: {s.date}",
            f"Total planned: {format_minutes_short(s.planned_minutes)}",
            f"Total completed: {format_minutes_short(s.completed_minutes)}",
            f"Tasks completed: {s.tasks_completed}/{s.tasks_total}",
            f"Tasks missed: {s.tasks_missed}",
            f"Completion: {int(s.completion_pct)}%",
            "",
            "Task breakdown:",
            s.details or "(no details)",
        ]
        self.detail_text.insert("1.0", "\n".join(lines))