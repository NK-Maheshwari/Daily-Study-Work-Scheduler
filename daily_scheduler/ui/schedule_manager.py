"""Schedule Manager screen - CRUD for today's tasks and recurring templates."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from database import Database
from models import (
    RECURRING_TYPES,
    TASK_TYPES,
    WEEKDAY_NAMES,
    Task,
    parse_time,
    today_str,
)
from scheduler import Scheduler
from ui.theme import apply_theme


class ScheduleManager(tk.Toplevel):
    def __init__(self, parent, db: Database, scheduler: Scheduler,
                 task: Optional[Task] = None, on_change=None):
        super().__init__(parent)
        self.db = db
        self.scheduler = scheduler
        self.on_change = on_change
        self.editing_id: Optional[int] = None
        self.theme = parent.theme

        self.title("Schedule Manager")
        self.geometry("780x720")
        self.configure(bg=self.theme["bg"])
        self.transient(parent)

        self._build_subject_bar()
        self._build_form()
        self._build_list()
        self._refresh_subjects()
        self._refresh_list()

        if task is not None:
            self._load_task(task)
        self.grab_set()

    # ---- subject quick bar ------------------------------------------------
    def _build_subject_bar(self) -> None:
        t = self.theme
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=12, pady=(10, 4))
        ttk.Label(bar, text="Subjects:", style="MutedBg.TLabel").pack(
            side="left")
        self.subject_combo = ttk.Combobox(bar, values=[], width=18)
        self.subject_combo.pack(side="left", padx=6)
        self.topic_combo = ttk.Combobox(bar, values=[], width=18)
        self.topic_combo.pack(side="left", padx=6)
        ttk.Button(bar, text="Add Subject",
                   command=self._add_subject).pack(side="left", padx=4)
        ttk.Button(bar, text="Add Topic",
                   command=self._add_topic).pack(side="left", padx=4)
        ttk.Button(bar, text="Delete Subject",
                   command=self._delete_subject).pack(side="left", padx=4)
        self.subject_combo.bind("<<ComboboxSelected>>",
                                lambda _e: self._update_topics())

    # ---- form -------------------------------------------------------------
    def _build_form(self) -> None:
        t = self.theme
        card = ttk.Frame(self, style="Card.TFrame")
        card.pack(fill="x", padx=12, pady=6)
        ttk.Label(card, text="Task Details", style="Card.TLabel",
                  font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=12,
                                                      pady=(8, 4))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x", padx=12, pady=8)

        self.f_subject = tk.StringVar()
        self.f_topic = tk.StringVar()
        self.f_start = tk.StringVar(value="09:00")
        self.f_duration = tk.StringVar(value="60")
        self.f_type = tk.StringVar(value="Study")
        self.f_recurring = tk.StringVar(value="Once")
        self.f_notes = tk.StringVar()
        self.f_recurring_days = {name: tk.BooleanVar() for name in WEEKDAY_NAMES}

        def entry_row(label, var, row, combo=False, values=None):
            ttk.Label(form, text=label, style="Card.TLabel").grid(
                row=row, column=0, sticky="w", pady=4)
            if combo:
                w = ttk.Combobox(form, textvariable=var, values=values or [],
                                 width=20)
            else:
                w = ttk.Entry(form, textvariable=var, width=22)
            w.grid(row=row, column=1, sticky="w", pady=4, padx=8)
            return w

        self.subject_entry = entry_row("Subject:", self.f_subject, 0,
                                       combo=True)
        self.subject_entry.bind("<<ComboboxSelected>>",
                                lambda _e: self._sync_topics_from_subject())
        self.topic_entry = entry_row("Topic:", self.f_topic, 1, combo=True)
        entry_row("Start Time (HH:MM):", self.f_start, 2)
        entry_row("Duration (min):", self.f_duration, 3)
        entry_row("Type:", self.f_type, 4, combo=True, values=TASK_TYPES)
        entry_row("Recurring:", self.f_recurring, 5, combo=True,
                  values=RECURRING_TYPES)

        # Recurring days (for Weekly)
        days_frame = ttk.Frame(form, style="Card.TFrame")
        days_frame.grid(row=6, column=1, sticky="w", pady=4)
        for name in WEEKDAY_NAMES:
            ttk.Checkbutton(days_frame, text=name,
                            variable=self.f_recurring_days[name],
                            style="Card.TLabel").pack(side="left", padx=2)
        ttk.Label(form, text="Weekdays (if Weekly):",
                  style="Card.TLabel").grid(row=6, column=0, sticky="w")

        ttk.Label(form, text="Notes:", style="Card.TLabel").grid(
            row=7, column=0, sticky="nw", pady=4)
        notes_entry = ttk.Entry(form, textvariable=self.f_notes, width=40)
        notes_entry.grid(row=7, column=1, sticky="w", pady=4, padx=8)

        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill="x", padx=12, pady=(4, 10))
        ttk.Button(btns, text="Add Task", command=self._add_task).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Update", command=self._update_task).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Delete", command=self._delete_task).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Clear", command=self._clear_form).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Reschedule Missed to End",
                   command=self._reschedule_missed).pack(side="right", padx=4)

    # ---- list -------------------------------------------------------------
    def _build_list(self) -> None:
        t = self.theme
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=12, pady=6)
        ttk.Label(wrap, text="Today's Tasks", style="Section.TLabel").pack(
            anchor="w")
        cols = ("id", "start", "subject", "topic", "dur", "type", "recur",
                "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=10)
        for c, w in zip(cols, (40, 60, 140, 140, 60, 80, 90, 90)):
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=(4, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

    # ---- data helpers -----------------------------------------------------
    def _refresh_subjects(self) -> None:
        names = self.db.get_subject_names()
        self.subject_combo.configure(values=names)
        self.subject_entry.configure(values=names)
        if names and not self.f_subject.get():
            self.f_subject.set(names[0])
            self._sync_topics_from_subject()

    def _update_topics(self) -> None:
        name = self.subject_combo.get()
        for s in self.db.get_subjects():
            if s.name == name:
                self.topic_combo.configure(values=s.topics)
                return

    def _sync_topics_from_subject(self) -> None:
        name = self.f_subject.get()
        for s in self.db.get_subjects():
            if s.name == name:
                self.topic_entry.configure(values=s.topics)
                return
        self.topic_entry.configure(values=[])

    def _add_subject(self) -> None:
        name = self.subject_combo.get().strip()
        if not name:
            return
        self.db.add_subject(name)
        self._refresh_subjects()
        messagebox.showinfo("Subject", f"Subject '{name}' added.")

    def _add_topic(self) -> None:
        subj = self.subject_combo.get().strip()
        topic = self.topic_combo.get().strip()
        if not subj or not topic:
            return
        self.db.add_topic(subj, topic)
        self._refresh_subjects()
        self._sync_topics_from_subject()

    def _delete_subject(self) -> None:
        name = self.subject_combo.get().strip()
        if name and messagebox.askyesno("Delete", f"Delete subject '{name}'?"):
            self.db.delete_subject(name)
            self._refresh_subjects()

    def _collect_task(self) -> Optional[Task]:
        subject = self.f_subject.get().strip()
        if not subject:
            messagebox.showerror("Error", "Subject is required.")
            return None
        start = self.f_start.get().strip()
        if parse_time(start) is None:
            messagebox.showerror("Error", "Start time must be HH:MM.")
            return None
        try:
            duration = int(self.f_duration.get())
            if duration <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Duration must be a positive integer.")
            return None
        days = ",".join(
            str(i) for i, name in enumerate(WEEKDAY_NAMES)
            if self.f_recurring_days[name].get()
        )
        task = Task(
            id=self.editing_id,
            date=today_str(),
            subject=subject,
            topic=self.f_topic.get().strip(),
            start_time=start,
            duration=duration,
            task_type=self.f_type.get(),
            notes=self.f_notes.get().strip(),
            recurring_type=self.f_recurring.get(),
            recurring_days=days,
        )
        return task

    def _add_task(self) -> None:
        task = self._collect_task()
        if task is None:
            return
        as_recurring = task.recurring_type != "Once"
        self.scheduler.add_task(task, as_recurring=as_recurring)
        self._notify_change()
        self._refresh_list()
        self._clear_form()
        messagebox.showinfo("Added", "Task added to today's schedule.")

    def _update_task(self) -> None:
        if self.editing_id is None:
            messagebox.showerror("Error", "Select a task to update.")
            return
        task = self._collect_task()
        if task is None:
            return
        self.scheduler.update_task(task)
        self._notify_change()
        self._refresh_list()
        messagebox.showinfo("Updated", "Task updated.")

    def _delete_task(self) -> None:
        if self.editing_id is None:
            messagebox.showerror("Error", "Select a task to delete.")
            return
        if messagebox.askyesno("Delete", "Delete this task?"):
            self.scheduler.remove_task(self.editing_id)
            self._notify_change()
            self._refresh_list()
            self._clear_form()

    def _reschedule_missed(self) -> None:
        self.scheduler.reschedule_missed_to_end()
        self._notify_change()
        self._refresh_list()
        messagebox.showinfo("Rescheduled", "Missed tasks moved to end of day.")

    def _clear_form(self) -> None:
        self.editing_id = None
        self.f_subject.set("")
        self.f_topic.set("")
        self.f_start.set("09:00")
        self.f_duration.set(self.db.get_setting("default_task_duration", "60"))
        self.f_type.set("Study")
        self.f_recurring.set("Once")
        self.f_notes.set("")
        for v in self.f_recurring_days.values():
            v.set(False)

    def _load_task(self, task: Task) -> None:
        self.editing_id = task.id
        self.f_subject.set(task.subject)
        self._sync_topics_from_subject()
        self.f_topic.set(task.topic)
        self.f_start.set(task.start_time)
        self.f_duration.set(str(task.duration))
        self.f_type.set(task.task_type)
        self.f_recurring.set(task.recurring_type)
        self.f_notes.set(task.notes)
        for v in self.f_recurring_days.values():
            v.set(False)
        if task.recurring_days:
            for d in task.recurring_days.split(","):
                if d != "":
                    self.f_recurring_days[WEEKDAY_NAMES[int(d)]].set(True)

    def _on_select(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        tid = int(self.tree.item(sel[0], "values")[0])
        for task in self.scheduler.tasks:
            if task.id == tid:
                self._load_task(task)
                return

    def _refresh_list(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for task in self.scheduler.tasks:
            recur = task.recurring_type
            if recur == "Weekly" and task.recurring_days:
                recur = "Weekly (" + ",".join(
                    WEEKDAY_NAMES[int(d)] for d in task.recurring_days.split(",")
                    if d != "") + ")"
            self.tree.insert("", "end", values=(
                task.id, task.start_time, task.subject, task.topic,
                f"{task.duration}m", task.task_type, recur, task.status,
            ))

    def _notify_change(self) -> None:
        if self.on_change:
            self.on_change()