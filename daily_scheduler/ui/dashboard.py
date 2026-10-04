"""Main dashboard window for the Daily Study & Work Scheduler."""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk
from typing import Optional

from database import Database
from models import (
    STATUS_ACTIVE,
    STATUS_COMPLETED,
    STATUS_MISSED,
    STATUS_SKIPPED,
    STATUS_UPCOMING,
    TASK_TYPES,
    Task,
    format_hhmm,
    format_minutes_short,
    format_seconds,
    today_str,
)
from scheduler import Scheduler
from timer import Timer
from ui.theme import apply_theme, status_color


def render_bar(fraction: float, width: int = 20) -> str:
    fraction = max(0.0, min(fraction, 1.0))
    filled = int(round(fraction * width))
    return "\u2588" * filled + "\u2591" * (width - filled)


class Dashboard(tk.Tk):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.title("Daily Study & Work Scheduler")
        self.geometry("1080x780")
        self.minsize(960, 700)

        self.theme_name = self.db.get_setting("theme", "light")
        self.theme = apply_theme(self, self.theme_name)

        self.scheduler = Scheduler(self.db)
        self.auto_start_next = self.db.get_setting("auto_start_next", "1") == "1"
        self.alarm_sound_on = self.db.get_setting("alarm_sound", "1") == "1"
        self.notifications_on = self.db.get_setting("notifications", "1") == "1"

        self._end_of_day_shown = False
        self._alarm_dialog: Optional[tk.Toplevel] = None

        self.timer = Timer(
            self, self.scheduler, self.on_tick, self._handle_alarm,
            interval_ms=int(self.db.get_setting("tick_interval_ms", "500")),
        )

        self._build_ui()
        self._refresh_schedule_table()

        # Initial state computation (handles late start / restart).
        self.scheduler.recompute_state()
        self.on_tick()
        self.timer.start()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- UI construction --------------------------------------------------
    def _build_ui(self) -> None:
        t = self.theme
        # Header
        header = ttk.Frame(self, style="Header.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="DAILY STUDY & WORK SCHEDULER",
                  style="Header.TLabel").pack(side="left", padx=20, pady=12)
        self.clock_label = ttk.Label(header, text="", style="Header.TLabel")
        self.clock_label.pack(side="right", padx=20, pady=12)

        # Top cards row
        top = ttk.Frame(self)
        top.pack(fill="x", padx=16, pady=(12, 6))
        self._build_current_card(top)
        self._build_next_card(top)

        # Guidance strip
        self.guidance_label = ttk.Label(self, text="", style="MutedBg.TLabel",
                                        anchor="w", font=("Segoe UI", 11))
        self.guidance_label.pack(fill="x", padx=20, pady=(2, 6))

        # Progress section
        self._build_progress_section()

        # Controls
        self._build_controls()

        # Schedule table
        self._build_schedule_section()

        # Status bar
        self.status_bar = ttk.Label(self, text="Ready", style="MutedBg.TLabel",
                                    anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=12, pady=4)

    def _card(self, parent, title, side, expand=True):
        t = self.theme
        frame = ttk.Frame(parent, style="Card.TFrame", relief="flat",
                          borderwidth=1)
        frame.pack(side=side, fill="both", expand=expand, padx=8)
        # Title bar
        ttl = ttk.Frame(frame, style="CardAlt.TFrame")
        ttl.pack(fill="x")
        ttk.Label(ttl, text=title, style="CardAlt.TLabel",
                  font=("Segoe UI", 11, "bold")).pack(side="left", padx=12,
                                                       pady=6)
        body = ttk.Frame(frame, style="Card.TFrame")
        body.pack(fill="both", expand=True, padx=12, pady=8)
        return frame, body

    def _build_current_card(self, parent) -> None:
        frame, body = self._card(parent, "CURRENT TASK", "left")
        self.current_frame = frame
        self.cur_subject = ttk.Label(body, text="\u2014", style="Subject.TLabel")
        self.cur_subject.pack(anchor="w")
        self.cur_topic = ttk.Label(body, text="", style="Topic.TLabel")
        self.cur_topic.pack(anchor="w")
        self.cur_meta = ttk.Label(body, text="", style="Muted.TLabel")
        self.cur_meta.pack(anchor="w", pady=(6, 0))
        self.cur_time = ttk.Label(body, text="--:--:--", style="Big.TLabel")
        self.cur_time.pack(anchor="w", pady=(8, 2))
        self.cur_bar_label = ttk.Label(body, text=render_bar(0), style="Card.TLabel",
                                       font=("Consolas", 12))
        self.cur_bar_label.pack(anchor="w")
        self.cur_progress_label = ttk.Label(body, text="0%", style="Muted.TLabel")
        self.cur_progress_label.pack(anchor="w")
        self.cur_status = ttk.Label(body, text="IDLE", style="Card.TLabel",
                                    font=("Segoe UI", 12, "bold"))
        self.cur_status.pack(anchor="w", pady=(8, 0))

    def _build_next_card(self, parent) -> None:
        frame, body = self._card(parent, "UP NEXT", "right")
        self.next_subject = ttk.Label(body, text="\u2014", style="Subject.TLabel")
        self.next_subject.pack(anchor="w")
        self.next_topic = ttk.Label(body, text="", style="Topic.TLabel")
        self.next_topic.pack(anchor="w")
        self.next_meta = ttk.Label(body, text="", style="Muted.TLabel")
        self.next_meta.pack(anchor="w", pady=(6, 0))
        self.next_countdown = ttk.Label(body, text="", style="Card.TLabel",
                                        font=("Consolas", 20, "bold"),
                                        foreground=self.theme["accent"])
        self.next_countdown.pack(anchor="w", pady=(8, 0))

    def _build_progress_section(self) -> None:
        t = self.theme
        wrap = ttk.Frame(self)
        wrap.pack(fill="x", padx=16, pady=6)
        ttk.Label(wrap, text="TODAY'S PROGRESS", style="Section.TLabel").pack(
            anchor="w")
        row = ttk.Frame(wrap)
        row.pack(fill="x", pady=(4, 0))
        self.progress_summary = ttk.Label(row, text="", style="MutedBg.TLabel",
                                          font=("Segoe UI", 11))
        self.progress_summary.pack(side="left")
        self.overall_bar = ttk.Progressbar(row, length=320, maximum=100,
                                           style="Horizontal.TProgressbar")
        self.overall_bar.pack(side="right", padx=12)
        self.overall_pct = ttk.Label(row, text="0%", style="MutedBg.TLabel",
                                     font=("Segoe UI", 11, "bold"))
        self.overall_pct.pack(side="right")

    def _build_controls(self) -> None:
        t = self.theme
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=16, pady=6)
        self.btn_pause = ttk.Button(bar, text="Pause", command=self.do_pause)
        self.btn_resume = ttk.Button(bar, text="Resume", command=self.do_resume,
                                     state="disabled")
        self.btn_skip = ttk.Button(bar, text="Skip", command=self.do_skip)
        self.btn_extend5 = ttk.Button(bar, text="+5 Min",
                                      command=lambda: self.do_extend(5))
        self.btn_extend10 = ttk.Button(bar, text="+10 Min",
                                       command=lambda: self.do_extend(10))
        self.btn_snooze = ttk.Button(bar, text="Snooze 5",
                                     command=lambda: self.do_snooze(5))
        self.btn_schedule = ttk.Button(bar, text="Schedule Manager",
                                       command=self.open_schedule_manager)
        self.btn_history = ttk.Button(bar, text="History",
                                      command=self.open_history)
        self.btn_settings = ttk.Button(bar, text="Settings",
                                       command=self.open_settings)
        for b in (self.btn_pause, self.btn_resume, self.btn_skip,
                  self.btn_extend5, self.btn_extend10, self.btn_snooze):
            b.pack(side="left", padx=4)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y",
                                                    padx=8)
        self.btn_schedule.pack(side="left", padx=4)
        self.btn_history.pack(side="left", padx=4)
        self.btn_settings.pack(side="right", padx=4)

    def _build_schedule_section(self) -> None:
        t = self.theme
        wrap = ttk.Frame(self)
        wrap.pack(fill="both", expand=True, padx=16, pady=(6, 12))
        ttk.Label(wrap, text="TODAY'S SCHEDULE", style="Section.TLabel").pack(
            anchor="w")
        cols = ("start", "end", "subject", "topic", "duration", "type", "status")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=9)
        widths = {"start": 70, "end": 70, "subject": 170, "topic": 170,
                  "duration": 80, "type": 90, "status": 120}
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.tag_configure("completed", foreground=self.theme["completed"])
        self.tree.tag_configure("active", foreground=self.theme["active"])
        self.tree.tag_configure("upcoming", foreground=self.theme["upcoming"])
        self.tree.tag_configure("missed", foreground=self.theme["missed"])
        self.tree.tag_configure("skipped", foreground=self.theme["skipped"])
        self.tree.pack(fill="both", expand=True, pady=(4, 0))
        self.tree.bind("<Double-1>", self._on_tree_double)

    # ---- tick / refresh ---------------------------------------------------
    def on_tick(self) -> None:
        now = datetime.now()
        # Detect date change -> reload.
        if self.scheduler.today != today_str():
            self.scheduler.reload()
            self.scheduler.recompute_state(now)
            self._end_of_day_shown = False
        else:
            self.scheduler.recompute_state(now)

        # Activate the task whose window contains now.
        transition = self.scheduler.transition_into_active(now)
        if transition is not None and self.notifications_on:
            self._notify_start(transition)

        active = self.scheduler.get_active_task(now)
        nxt = self.scheduler.get_next_task(now)

        self._update_current_card(active, now)
        self._update_next_card(nxt, active, now)
        self._update_progress(now)
        self._update_guidance(active, nxt, now)
        self._refresh_schedule_table()
        self._update_clock(now)
        self._update_buttons(active)

        # Alarm check
        if active and active.remaining_seconds(now) <= 0 and not active.alarm_fired:
            active.alarm_fired = True
            self._handle_alarm(active, now)

        # End of day
        progress = self.scheduler.daily_progress(now)
        if progress["all_done"] and not self._end_of_day_shown:
            self._end_of_day_shown = True
            self._show_end_of_day(progress)

    def _update_clock(self, now: datetime) -> None:
        self.clock_label.configure(text=now.strftime("%A, %B %d  %H:%M:%S"))

    def _update_current_card(self, active: Optional[Task], now: datetime) -> None:
        t = self.theme
        if active is None:
            self.cur_subject.configure(text="\u2014", foreground=t["muted"])
            self.cur_topic.configure(text="No active task")
            self.cur_meta.configure(text="")
            self.cur_time.configure(text="--:--:--", foreground=t["muted"])
            self.cur_bar_label.configure(text=render_bar(0))
            self.cur_progress_label.configure(text="0%")
            self.cur_status.configure(text="IDLE", foreground=t["muted"])
            return

        remaining = active.remaining_seconds(now)
        frac = active.progress_fraction(now)
        if active.is_break:
            self.cur_subject.configure(text="BREAK TIME", foreground=t["completed"])
        else:
            self.cur_subject.configure(text=active.subject or "Task",
                                       foreground=t["fg"])
        self.cur_topic.configure(text=active.topic or "")
        self.cur_meta.configure(
            text=f"Started: {format_hhmm(active.start_time)}   "
                 f"Allocated: {active.duration} min   Type: {active.task_type}"
        )
        color = t["missed"] if remaining < 0 else t["accent"]
        self.cur_time.configure(text=format_seconds(remaining), foreground=color)
        self.cur_bar_label.configure(text=render_bar(frac))
        self.cur_progress_label.configure(text=f"{int(frac*100)}%")
        if active.paused:
            self.cur_status.configure(text="\u23f8 PAUSED", foreground=t["skipped"])
        elif remaining <= 0:
            self.cur_status.configure(text="TIME COMPLETE!", foreground=t["missed"])
        else:
            self.cur_status.configure(text="\u25b6 IN PROGRESS",
                                      foreground=t["active"])

    def _update_next_card(self, nxt: Optional[Task], active: Optional[Task],
                          now: datetime) -> None:
        t = self.theme
        if nxt is None:
            self.next_subject.configure(text="\u2014", foreground=t["muted"])
            self.next_topic.configure(text="No more tasks today")
            self.next_meta.configure(text="")
            self.next_countdown.configure(text="")
            return
        self.next_subject.configure(text=nxt.subject or "Task", foreground=t["fg"])
        self.next_topic.configure(text=nxt.topic or "")
        self.next_meta.configure(
            text=f"Start: {format_hhmm(nxt.start_time)}   "
                 f"Duration: {nxt.duration} min   Type: {nxt.task_type}"
        )
        delta = nxt.start_datetime() - now
        mins = int(delta.total_seconds() // 60)
        if mins > 0:
            self.next_countdown.configure(
                text=f"Starts in {mins} min", foreground=t["accent"])
        else:
            self.next_countdown.configure(text="Starting soon",
                                          foreground=t["accent"])

    def _update_progress(self, now: datetime) -> None:
        p = self.scheduler.daily_progress(now)
        self.progress_summary.configure(
            text=(f"Completed: {p['completed_tasks']}/{p['total_tasks']} tasks   "
                  f"Worked: {format_minutes_short(p['completed_seconds']//60)}   "
                  f"Remaining: {format_minutes_short(p['remaining_seconds']//60)}   "
                  f"Planned: {format_minutes_short(p['total_planned_seconds']//60)}   "
                  f"Missed: {p['missed_tasks']}")
        )
        self.overall_bar["value"] = p["completion_pct"]
        self.overall_pct.configure(text=f"{int(p['completion_pct'])}%")

    def _update_guidance(self, active: Optional[Task], nxt: Optional[Task],
                         now: datetime) -> None:
        t = self.theme
        if active:
            remaining = max(active.remaining_seconds(now), 0)
            text = (f"NOW  \u2192  {active.subject} \u2014 {active.topic}   "
                    f"|   Remaining: {format_minutes_short(remaining//60)}")
        elif self.scheduler.has_schedule():
            p = self.scheduler.daily_progress(now)
            if p["all_done"]:
                text = "\U0001f389 You have completed today's schedule!"
            else:
                missed = self.scheduler.get_missed_tasks()
                if missed:
                    names = ", ".join(f"{m.subject} ({m.start_time})" for m in missed)
                    text = (f"You missed: {names}.  "
                            "Open Schedule Manager to reschedule.")
                else:
                    text = "No task is active right now. Waiting for the next slot."
        else:
            text = ("No schedule created for today.  "
                    "Click 'Schedule Manager' to create today's schedule.")
        self.guidance_label.configure(text=text)

    def _update_buttons(self, active: Optional[Task]) -> None:
        if active and active.status == STATUS_ACTIVE:
            if active.paused:
                self.btn_pause.configure(state="disabled")
                self.btn_resume.configure(state="normal")
            else:
                self.btn_pause.configure(state="normal")
                self.btn_resume.configure(state="disabled")
            self.btn_skip.configure(state="normal")
            self.btn_extend5.configure(state="normal")
            self.btn_extend10.configure(state="normal")
            self.btn_snooze.configure(state="normal")
        else:
            self.btn_pause.configure(state="disabled")
            self.btn_resume.configure(state="disabled")
            self.btn_skip.configure(state="disabled")
            self.btn_extend5.configure(state="disabled")
            self.btn_extend10.configure(state="disabled")
            self.btn_snooze.configure(state="disabled")

    # ---- schedule table ---------------------------------------------------
    def _refresh_schedule_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for task in self.scheduler.tasks:
            tag = task.status
            sym = {
                STATUS_COMPLETED: "\u2713 Completed",
                STATUS_ACTIVE: "\u25b6 Active",
                STATUS_UPCOMING: "Upcoming",
                STATUS_MISSED: "Missed",
                STATUS_SKIPPED: "Skipped",
            }[task.status]
            self.tree.insert(
                "", "end",
                values=(task.start_time, task.end_time_str(),
                        task.subject, task.topic,
                        f"{task.duration} min", task.task_type, sym),
                tags=(tag,),
            )

    def _on_tree_double(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        values = self.tree.item(sel[0], "values")
        if not values:
            return
        start_time = values[0]
        for task in self.scheduler.tasks:
            if task.start_time == start_time and task.subject == values[2]:
                self.open_schedule_manager(task)
                return

    # ---- notifications ----------------------------------------------------
    def _notify_start(self, task: Task) -> None:
        if self.alarm_sound_on:
            Timer.play_start_chime()
        msg = (f"\U0001f514 Task Started\n"
               f"{task.subject} \u2014 {task.topic}\n"
               f"You have {task.duration} minutes.")
        self._toast(msg, color_key="active")
        self.status_bar.configure(text=msg.replace("\n", "  |  "))

    def _toast(self, text: str, color_key: str = "accent",
               duration_ms: int = 4000) -> None:
        t = self.theme
        win = tk.Toplevel(self)
        win.configure(bg=t[color_key])
        win.overrideredirect(True)
        lbl = tk.Label(win, text=text, bg=t[color_key], fg="#ffffff",
                       font=("Segoe UI", 11, "bold"), padx=18, pady=12,
                       justify="left")
        lbl.pack()
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() - 320
        y = self.winfo_y() + 60
        win.geometry(f"+{x}+{y}")
        win.lift()
        win.after(duration_ms, win.destroy)

    # ---- alarm ------------------------------------------------------------
    def _handle_alarm(self, task: Task, now: datetime) -> None:
        if self.alarm_sound_on:
            Timer.play_alarm()
        nxt = self.scheduler.get_next_task(now)
        if self.auto_start_next:
            self.scheduler.complete_active(task, now)
            self._toast(
                f"\u23f0 Time Complete\n{task.subject} \u2014 {task.topic}\n"
                + (f"Next: {nxt.subject} \u2014 {nxt.topic}"
                   if nxt else "No more tasks."),
                color_key="missed",
            )
            return
        self._show_alarm_dialog(task, nxt, now)

    def _show_alarm_dialog(self, task: Task, nxt: Optional[Task],
                           now: datetime) -> None:
        if self._alarm_dialog is not None:
            try:
                self._alarm_dialog.destroy()
            except tk.TclError:
                pass
        t = self.theme
        dlg = tk.Toplevel(self)
        dlg.title("Time Complete!")
        dlg.configure(bg=t["alarm_bg"])
        dlg.transient(self)
        dlg.grab_set()
        self._alarm_dialog = dlg

        tk.Label(dlg, text="TIME COMPLETE!", bg=t["alarm_bg"],
                 fg="#ffffff", font=("Segoe UI", 18, "bold"),
                 padx=20, pady=14).pack()
        body = tk.Frame(dlg, bg=t["card"])
        body.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(body, text=f"{task.subject} \u2014 {task.topic}", bg=t["card"],
                 fg=t["fg"], font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(body, text=f"Your scheduled {task.duration} minutes are complete.",
                 bg=t["card"], fg=t["fg"]).pack(anchor="w", pady=(4, 8))
        if nxt:
            tk.Label(body, text=f"Next task: {nxt.subject} \u2014 {nxt.topic}",
                     bg=t["card"], fg=t["accent"],
                     font=("Segoe UI", 11, "bold")).pack(anchor="w")
        else:
            tk.Label(body, text="This was the last task of the day.",
                     bg=t["card"], fg=t["muted"]).pack(anchor="w")

        btns = tk.Frame(dlg, bg=t["card"])
        btns.pack(fill="x", pady=10)

        def close():
            dlg.grab_release()
            dlg.destroy()
            self._alarm_dialog = None

        def start_next():
            self.scheduler.complete_active(task, datetime.now())
            close()

        def snooze():
            self.scheduler.snooze_task(task, 5)
            close()

        def extend():
            self.scheduler.extend_task(task, 10)
            close()

        def skip():
            self.scheduler.skip_task(task)
            close()

        ttk.Button(btns, text="Start Next Task", command=start_next).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Snooze 5 Minutes", command=snooze).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Extend +10 Min", command=extend).pack(
            side="left", padx=4)
        ttk.Button(btns, text="Skip Task", command=skip).pack(
            side="left", padx=4)
        dlg.update_idletasks()
        dlg.geometry(f"+{self.winfo_x()+200}+{self.winfo_y()+150}")

    # ---- control actions --------------------------------------------------
    def _current_active(self) -> Optional[Task]:
        return self.scheduler.get_active_task(datetime.now())

    def do_pause(self) -> None:
        a = self._current_active()
        if a:
            self.scheduler.pause_task(a)
            self.status_bar.configure(text=f"Paused: {a.subject}")

    def do_resume(self) -> None:
        a = self._current_active()
        if a:
            self.scheduler.resume_task(a)
            self.status_bar.configure(text=f"Resumed: {a.subject}")

    def do_skip(self) -> None:
        a = self._current_active()
        if a and messagebox.askyesno("Skip Task",
                                     f"Skip {a.subject} \u2014 {a.topic}?"):
            self.scheduler.skip_task(a)
            self.status_bar.configure(text=f"Skipped: {a.subject}")

    def do_extend(self, minutes: int) -> None:
        a = self._current_active()
        if a:
            self.scheduler.extend_task(a, minutes)
            self.status_bar.configure(
                text=f"Extended {a.subject} by {minutes} min")

    def do_snooze(self, minutes: int) -> None:
        a = self._current_active()
        if a:
            self.scheduler.snooze_task(a, minutes)
            self.status_bar.configure(
                text=f"Snoozed {a.subject} for {minutes} min")

    # ---- end of day -------------------------------------------------------
    def _show_end_of_day(self, progress: dict) -> None:
        t = self.theme
        dlg = tk.Toplevel(self)
        dlg.title("Today Complete")
        dlg.configure(bg=t["card"])
        dlg.transient(self)
        dlg.grab_set()
        tk.Label(dlg, text="\U0001f389 TODAY COMPLETE", bg=t["card"],
                 fg=t["completed"], font=("Segoe UI", 20, "bold"),
                 padx=20, pady=16).pack()
        info = tk.Frame(dlg, bg=t["card"])
        info.pack(padx=20, pady=8)
        rows = [
            ("Total planned", format_minutes_short(
                progress["total_planned_seconds"] // 60)),
            ("Total completed", format_minutes_short(
                progress["completed_seconds"] // 60)),
            ("Tasks completed", f"{progress['completed_tasks']}/"
                                f"{progress['total_tasks']}"),
            ("Completion", f"{int(progress['completion_pct'])}%"),
        ]
        for i, (k, v) in enumerate(rows):
            tk.Label(info, text=k, bg=t["card"], fg=t["muted"],
                     font=("Segoe UI", 11)).grid(row=i, column=0, sticky="w",
                                                 pady=2)
            tk.Label(info, text=v, bg=t["card"], fg=t["fg"],
                     font=("Segoe UI", 11, "bold")).grid(row=i, column=1,
                                                         sticky="w", pady=2,
                                                         padx=12)
        btns = tk.Frame(dlg, bg=t["card"])
        btns.pack(pady=12)
        ttk.Button(btns, text="View History",
                   command=lambda: [dlg.destroy(), self.open_history()]).pack(
            side="left", padx=6)
        ttk.Button(btns, text="Plan Tomorrow",
                   command=lambda: [dlg.destroy(), self.open_schedule_manager()]
                   ).pack(side="left", padx=6)
        ttk.Button(btns, text="Close", command=dlg.destroy).pack(
            side="left", padx=6)
        dlg.update_idletasks()
        dlg.geometry(f"+{self.winfo_x()+250}+{self.winfo_y()+150}")

    # ---- sub-windows ------------------------------------------------------
    def open_schedule_manager(self, task: Optional[Task] = None):
        from ui.schedule_manager import ScheduleManager
        return ScheduleManager(self, self.db, self.scheduler, task,
                               on_change=self._after_schedule_change)

    def open_history(self) -> "HistoryWindow":
        from ui.history import HistoryWindow
        return HistoryWindow(self, self.db)

    def open_settings(self) -> "SettingsWindow":
        from ui.settings import SettingsWindow
        return SettingsWindow(self, self.db, on_change=self._apply_settings)

    def _after_schedule_change(self) -> None:
        self.scheduler.reload()
        self.scheduler.recompute_state()
        self._end_of_day_shown = False
        self._refresh_schedule_table()

    def _apply_settings(self) -> None:
        self.theme_name = self.db.get_setting("theme", "light")
        self.theme = apply_theme(self, self.theme_name)
        self.auto_start_next = self.db.get_setting("auto_start_next", "1") == "1"
        self.alarm_sound_on = self.db.get_setting("alarm_sound", "1") == "1"
        self.notifications_on = self.db.get_setting("notifications", "1") == "1"
        self.timer.set_interval(int(self.db.get_setting("tick_interval_ms",
                                                         "500")))
        # Re-apply table tag colours.
        self.tree.tag_configure("completed", foreground=self.theme["completed"])
        self.tree.tag_configure("active", foreground=self.theme["active"])
        self.tree.tag_configure("upcoming", foreground=self.theme["upcoming"])
        self.tree.tag_configure("missed", foreground=self.theme["missed"])
        self.tree.tag_configure("skipped", foreground=self.theme["skipped"])

    def _on_close(self) -> None:
        # Persist final working time for the active task.
        active = self.scheduler.get_active_task(datetime.now())
        if active:
            self.scheduler.db.set_task_status(
                active.id, active.status,
                working_seconds=active.elapsed_seconds(),
                pause_seconds=active.total_pause_seconds,
                duration=active.duration,
            )
        self.scheduler._maybe_record_history()
        self.timer.stop()
        self.destroy()