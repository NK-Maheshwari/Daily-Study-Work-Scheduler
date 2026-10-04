"""Core scheduling engine.

Determines the active task, upcoming tasks and missed tasks from the real
system clock (never by decrementing a counter).  Also expands recurring
templates into concrete tasks for a given day.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from database import Database
from models import (
    STATUS_ACTIVE,
    STATUS_COMPLETED,
    STATUS_MISSED,
    STATUS_SKIPPED,
    STATUS_UPCOMING,
    DaySummary,
    Task,
    today_str,
    WEEKDAY_NAMES,
    format_seconds,
)


class Scheduler:
    def __init__(self, db: Database):
        self.db = db
        self.today: str = today_str()
        self.tasks: List[Task] = []
        self._last_active_id: Optional[int] = None
        self.refresh_day()

    # ---- day / template management ----------------------------------------
    def refresh_day(self) -> None:
        """(Re)load today's concrete tasks, expanding templates if needed."""
        self.today = today_str()
        self.tasks = self.db.get_tasks_for_date(self.today)
        if not self.tasks:
            self._expand_templates_for_today()
            self.tasks = self.db.get_tasks_for_date(self.today)
        self.tasks.sort(key=lambda t: t.start_minutes)

    def _expand_templates_for_today(self) -> None:
        templates = self.db.get_templates()
        today_date = date.today()
        weekday = today_date.weekday()  # 0=Mon..6=Sun
        for tpl in templates:
            if not self._template_applies(tpl, weekday):
                continue
            concrete = Task(
                date=self.today,
                subject=tpl.subject,
                topic=tpl.topic,
                start_time=tpl.start_time,
                duration=tpl.duration,
                task_type=tpl.task_type,
                notes=tpl.notes,
                status=STATUS_UPCOMING,
                recurring_type=tpl.recurring_type,
                recurring_days=tpl.recurring_days,
            )
            self.db.save_task(concrete)

    @staticmethod
    def _template_applies(tpl: Task, weekday: int) -> bool:
        rt = tpl.recurring_type
        if rt == "Every day":
            return True
        if rt == "Weekdays":
            return weekday < 5
        if rt == "Weekends":
            return weekday >= 5
        if rt == "Weekly":
            try:
                days = [int(d) for d in tpl.recurring_days.split(",") if d != ""]
            except ValueError:
                days = []
            return weekday in days
        # "Once" templates are not auto-expanded (they are one-offs already
        # stored with a concrete date when created).
        return False

    def has_schedule(self) -> bool:
        return bool(self.tasks)

    # ---- state computation ------------------------------------------------
    def recompute_state(self, now: Optional[datetime] = None) -> None:
        """Mark completed/missed tasks based on the system clock.

        Called on startup and on every tick before reading the active task.
        """
        now = now or datetime.now()
        changed = False
        for task in self.tasks:
            end_dt = task.end_datetime()
            if task.status in (STATUS_COMPLETED, STATUS_SKIPPED):
                continue
            if now >= end_dt:
                # Task's window has fully passed.
                if task.status == STATUS_ACTIVE:
                    # Was active and ran its course -> completed.
                    task.actual_working_seconds = task.elapsed_seconds(now)
                    task.status = STATUS_COMPLETED
                    self.db.set_task_status(
                        task.id, STATUS_COMPLETED,
                        working_seconds=task.actual_working_seconds,
                    )
                    changed = True
                elif task.status == STATUS_UPCOMING:
                    task.status = STATUS_MISSED
                    self.db.set_task_status(task.id, STATUS_MISSED)
                    changed = True
        if changed:
            self._maybe_record_history()

    def get_active_task(self, now: Optional[datetime] = None) -> Optional[Task]:
        now = now or datetime.now()
        for task in self.tasks:
            if task.status in (STATUS_COMPLETED, STATUS_SKIPPED, STATUS_MISSED):
                continue
            if task.contains(now):
                return task
        return None

    def get_next_task(self, now: Optional[datetime] = None) -> Optional[Task]:
        now = now or datetime.now()
        for task in self.tasks:
            if task.status in (STATUS_COMPLETED, STATUS_SKIPPED, STATUS_MISSED):
                continue
            if task.start_datetime() > now:
                return task
        return None

    def get_missed_tasks(self) -> List[Task]:
        return [t for t in self.tasks if t.status == STATUS_MISSED]

    def activate(self, task: Task, now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        task.status = STATUS_ACTIVE
        task.notified_start = False
        self.db.set_task_status(task.id, STATUS_ACTIVE)

    def transition_into_active(self, now: Optional[datetime] = None) -> Optional[Task]:
        """If a task's window now contains `now`, mark it active (if not yet).

        Returns the task that just became active (transition) so the caller can
        fire a 'task started' notification, or None.
        """
        now = now or datetime.now()
        active = self.get_active_task(now)
        if active is None:
            self._last_active_id = None
            return None
        if active.status != STATUS_ACTIVE:
            self.activate(active, now)
            self._last_active_id = active.id
            return active
        self._last_active_id = active.id
        return None

    # ---- task control operations -----------------------------------------
    def complete_active(self, task: Task, now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        task.actual_working_seconds = task.elapsed_seconds(now)
        task.status = STATUS_COMPLETED
        task.alarm_fired = False
        self.db.set_task_status(
            task.id, STATUS_COMPLETED,
            working_seconds=task.actual_working_seconds,
        )
        self._maybe_record_history()

    def skip_task(self, task: Task) -> None:
        task.status = STATUS_SKIPPED
        task.alarm_fired = False
        self.db.set_task_status(task.id, STATUS_SKIPPED)
        self._maybe_record_history()

    def pause_task(self, task: Task, now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        if not task.paused:
            task.paused = True
            task.pause_start = now

    def resume_task(self, task: Task, now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        if task.paused and task.pause_start:
            delta = int((now - task.pause_start).total_seconds())
            task.total_pause_seconds += delta
            # Extend end time so the remaining work is preserved.
            task.duration += delta // 60
            task.paused = False
            task.pause_start = None
            self.db.set_task_status(
                task.id, task.status,
                pause_seconds=task.total_pause_seconds,
                duration=task.duration,
            )

    def extend_task(self, task: Task, minutes: int) -> None:
        if minutes <= 0:
            return
        task.duration += minutes
        task.alarm_fired = False
        task.snoozed_until = None
        self.db.set_task_status(task.id, task.status, duration=task.duration)

    def snooze_task(self, task: Task, minutes: int = 5,
                    now: Optional[datetime] = None) -> None:
        now = now or datetime.now()
        task.duration += minutes
        task.alarm_fired = False
        task.snoozed_until = now + timedelta(minutes=minutes)
        self.db.set_task_status(task.id, task.status, duration=task.duration)

    # ---- progress / summary ----------------------------------------------
    def daily_progress(self, now: Optional[datetime] = None) -> dict:
        now = now or datetime.now()
        total_planned = sum(t.duration for t in self.tasks)
        completed_tasks = [t for t in self.tasks if t.status == STATUS_COMPLETED]
        missed_tasks = [t for t in self.tasks if t.status == STATUS_MISSED]
        skipped = [t for t in self.tasks if t.status == STATUS_SKIPPED]
        completed_seconds = sum(t.actual_working_seconds for t in completed_tasks)

        active = self.get_active_task(now)
        if active:
            completed_seconds += active.elapsed_seconds(now)

        remaining_seconds = max(total_planned * 60 - completed_seconds, 0)
        total_count = len(self.tasks)
        done_count = len(completed_tasks)
        if total_count:
            completion_pct = (done_count / total_count) * 100
        else:
            completion_pct = 0.0

        return {
            "total_planned_seconds": total_planned * 60,
            "completed_seconds": completed_seconds,
            "remaining_seconds": remaining_seconds,
            "total_tasks": total_count,
            "completed_tasks": done_count,
            "missed_tasks": len(missed_tasks),
            "skipped_tasks": len(skipped),
            "completion_pct": completion_pct,
            "all_done": total_count > 0 and done_count + len(skipped) >= total_count,
        }

    def _maybe_record_history(self) -> None:
        progress = self.daily_progress()
        details_lines = []
        for t in self.tasks:
            if t.status == STATUS_COMPLETED:
                details_lines.append(
                    f"{t.subject} - {t.topic}: {t.duration} min (done)"
                )
            elif t.status == STATUS_MISSED:
                details_lines.append(
                    f"{t.subject} - {t.topic}: missed"
                )
        summary = DaySummary(
            date=self.today,
            total_planned_seconds=progress["total_planned_seconds"],
            total_completed_seconds=progress["completed_seconds"],
            tasks_total=progress["total_tasks"],
            tasks_completed=progress["completed_tasks"],
            tasks_missed=progress["missed_tasks"],
            completion_pct=progress["completion_pct"],
            details="\n".join(details_lines),
        )
        self.db.save_summary(summary)

    # ---- CRUD helpers used by the manager UI ------------------------------
    def add_task(self, task: Task, as_recurring: bool = False) -> Task:
        if as_recurring and task.recurring_type != "Once":
            template = Task(
                date=None,
                subject=task.subject,
                topic=task.topic,
                start_time=task.start_time,
                duration=task.duration,
                task_type=task.task_type,
                notes=task.notes,
                status=STATUS_UPCOMING,
                recurring_type=task.recurring_type,
                recurring_days=task.recurring_days,
            )
            self.db.save_task(template)
        task.date = self.today
        task.status = STATUS_UPCOMING
        self.db.save_task(task)
        self.refresh_day()
        return task

    def update_task(self, task: Task) -> None:
        self.db.save_task(task)
        self.refresh_day()

    def remove_task(self, task_id: int) -> None:
        self.db.delete_task(task_id)
        self.refresh_day()

    def reschedule_missed_to_end(self, now: Optional[datetime] = None) -> None:
        """Push missed tasks to the end of today's schedule."""
        now = now or datetime.now()
        missed = self.get_missed_tasks()
        if not missed:
            return
        last_end = max((t.end_minutes for t in self.tasks), default=0)
        last_end = max(last_end, now.hour * 60 + now.minute)
        for m in missed:
            m.start_time = f"{last_end // 60:02d}:{last_end % 60:02d}"
            m.status = STATUS_UPCOMING
            self.db.save_task(m)
            last_end += m.duration
        self.refresh_day()

    def reload(self) -> None:
        self.refresh_day()