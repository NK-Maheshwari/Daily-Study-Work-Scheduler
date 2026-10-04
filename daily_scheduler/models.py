"""Data models for the Daily Study & Work Scheduler."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, date, time as dtime, timedelta
from typing import List, Optional


# --- Constants ---------------------------------------------------------------

TASK_TYPES = ["Study", "Work", "Break", "Exercise", "Personal", "Other"]
RECURRING_TYPES = ["Once", "Every day", "Weekdays", "Weekends", "Weekly"]
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

STATUS_UPCOMING = "upcoming"
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUS_MISSED = "missed"
STATUS_SKIPPED = "skipped"

STATUS_LABELS = {
    STATUS_UPCOMING: "Upcoming",
    STATUS_ACTIVE: "Active",
    STATUS_COMPLETED: "Completed",
    STATUS_MISSED: "Missed",
    STATUS_SKIPPED: "Skipped",
}

# Status -> (display symbol, color tag)
STATUS_DISPLAY = {
    STATUS_UPCOMING: ("Upcoming", "gray"),
    STATUS_ACTIVE: ("\u25b6 Active", "blue"),
    STATUS_COMPLETED: ("\u2713 Completed", "green"),
    STATUS_MISSED: ("Missed", "red"),
    STATUS_SKIPPED: ("Skipped", "orange"),
}


# --- Helpers -----------------------------------------------------------------

def parse_time(value: str) -> Optional[datetime.time]:
    """Parse an 'HH:MM' string into a time object. Returns None if invalid."""
    if not value:
        return None
    try:
        parts = value.strip().split(":")
        if len(parts) != 2:
            return None
        hour, minute = int(parts[0]), int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return dtime(hour, minute)
    except (ValueError, AttributeError):
        pass
    return None


def time_to_minutes(value: str) -> int:
    """Convert 'HH:MM' to minutes since midnight. Invalid -> 0."""
    t = parse_time(value)
    if t is None:
        return 0
    return t.hour * 60 + t.minute


def minutes_to_time_str(minutes: int) -> str:
    """Convert minutes since midnight to 'HH:MM'."""
    minutes = minutes % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def format_hhmm(value: str) -> str:
    """Format 'HH:MM' to 'H:MM AM/PM' for display."""
    t = parse_time(value)
    if t is None:
        return value
    hour = t.hour
    suffix = "AM" if hour < 12 else "PM"
    disp = hour % 12
    if disp == 0:
        disp = 12
    return f"{disp}:{t.minute:02d} {suffix}"


def format_seconds(total_seconds: int) -> str:
    """Format seconds as 'HH:MM:SS' (or 'MM:SS' if < 1h)."""
    if total_seconds < 0:
        total_seconds = 0
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def format_minutes_short(total_minutes: int) -> str:
    """Format minutes as '3h 25m' / '45m'."""
    if total_minutes < 0:
        total_minutes = 0
    h = total_minutes // 60
    m = total_minutes % 60
    if h > 0 and m > 0:
        return f"{h}h {m}m"
    if h > 0:
        return f"{h}h"
    return f"{m}m"


def today_str() -> str:
    return date.today().isoformat()


# --- Data classes ------------------------------------------------------------

@dataclass
class Subject:
    id: Optional[int] = None
    name: str = ""
    topics: List[str] = field(default_factory=list)


@dataclass
class Task:
    id: Optional[int] = None
    date: Optional[str] = None          # 'YYYY-MM-DD'; None for recurring template
    subject: str = ""
    topic: str = ""
    start_time: str = "09:00"           # 'HH:MM'
    duration: int = 60                  # minutes (mutable; reflects extensions)
    task_type: str = "Study"
    notes: str = ""
    status: str = STATUS_UPCOMING
    actual_working_seconds: int = 0
    total_pause_seconds: int = 0
    recurring_type: str = "Once"
    recurring_days: str = ""            # comma-separated weekday ints (0=Mon..6=Sun)

    # --- Runtime-only fields (not persisted) ---
    paused: bool = False
    pause_start: Optional[datetime] = None
    alarm_fired: bool = False
    snoozed_until: Optional[datetime] = None
    notified_start: bool = False

    # ---- Time helpers ----
    @property
    def start_minutes(self) -> int:
        return time_to_minutes(self.start_time)

    @property
    def end_minutes(self) -> int:
        return self.start_minutes + self.duration

    def end_time_str(self) -> str:
        return minutes_to_time_str(self.end_minutes)

    def start_datetime(self, ref_date: Optional[date] = None) -> datetime:
        d = date.fromisoformat(self.date) if self.date else (ref_date or date.today())
        t = parse_time(self.start_time) or datetime.time(0, 0)
        return datetime.combine(d, t)

    def end_datetime(self, ref_date: Optional[date] = None) -> datetime:
        return self.start_datetime(ref_date) + timedelta(minutes=self.duration)

    @property
    def is_break(self) -> bool:
        return self.task_type == "Break"

    @property
    def is_template(self) -> bool:
        return self.date is None

    def remaining_seconds(self, now: Optional[datetime] = None) -> int:
        """Seconds remaining until the task ends (system-clock based)."""
        now = now or datetime.now()
        return int((self.end_datetime() - now).total_seconds())

    def elapsed_seconds(self, now: Optional[datetime] = None) -> int:
        """Working seconds elapsed since start, minus paused time."""
        now = now or datetime.now()
        start = self.start_datetime()
        if now < start:
            return 0
        elapsed = int((now - start).total_seconds()) - self.total_pause_seconds
        if self.paused and self.pause_start:
            elapsed -= int((now - self.pause_start).total_seconds())
        return max(elapsed, 0)

    def progress_fraction(self, now: Optional[datetime] = None) -> float:
        now = now or datetime.now()
        total = self.duration * 60
        if total <= 0:
            return 1.0
        return min(max(self.elapsed_seconds(now) / total, 0.0), 1.0)

    def contains(self, now: Optional[datetime] = None) -> bool:
        """True if `now` falls within the task's scheduled interval."""
        now = now or datetime.now()
        return self.start_datetime() <= now < self.end_datetime()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "date": self.date,
            "subject": self.subject,
            "topic": self.topic,
            "start_time": self.start_time,
            "duration": self.duration,
            "task_type": self.task_type,
            "notes": self.notes,
            "status": self.status,
            "actual_working_seconds": self.actual_working_seconds,
            "total_pause_seconds": self.total_pause_seconds,
            "recurring_type": self.recurring_type,
            "recurring_days": self.recurring_days,
        }


@dataclass
class DaySummary:
    date: str
    total_planned_seconds: int = 0
    total_completed_seconds: int = 0
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_missed: int = 0
    completion_pct: float = 0.0
    details: str = ""

    @property
    def planned_minutes(self) -> int:
        return self.total_planned_seconds // 60

    @property
    def completed_minutes(self) -> int:
        return self.total_completed_seconds // 60