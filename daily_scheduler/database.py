"""SQLite persistence layer for the Daily Study & Work Scheduler."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import date, datetime
from typing import Dict, List, Optional

from models import (
    STATUS_ACTIVE,
    STATUS_COMPLETED,
    STATUS_MISSED,
    STATUS_SKIPPED,
    STATUS_UPCOMING,
    Subject,
    Task,
    DaySummary,
    today_str,
    WEEKDAY_NAMES,
)


DEFAULT_SETTINGS: Dict[str, str] = {
    "alarm_sound": "1",
    "notifications": "1",
    "auto_start_next": "1",
    "default_task_duration": "60",
    "default_break_duration": "15",
    "theme": "light",
    "tick_interval_ms": "500",
}


class Database:
    """Thin SQLite wrapper. All schedule/progress data is persisted here."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()
        self._seed_settings()
        self._seed_default_subjects()

    # ---- schema -----------------------------------------------------------
    def _create_schema(self) -> None:
        c = self.conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS subjects (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT UNIQUE NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topics (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                subject_id  INTEGER NOT NULL,
                name        TEXT NOT NULL,
                UNIQUE(subject_id, name)
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                date                    TEXT,
                subject                 TEXT,
                topic                   TEXT,
                start_time              TEXT,
                duration                INTEGER,
                task_type               TEXT,
                notes                   TEXT,
                status                  TEXT,
                actual_working_seconds  INTEGER,
                total_pause_seconds     INTEGER,
                recurring_type          TEXT,
                recurring_days          TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key    TEXT PRIMARY KEY,
                value  TEXT
            );
            CREATE TABLE IF NOT EXISTS history (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                date                    TEXT UNIQUE,
                total_planned_seconds   INTEGER,
                total_completed_seconds INTEGER,
                tasks_total             INTEGER,
                tasks_completed         INTEGER,
                tasks_missed            INTEGER,
                completion_pct          REAL,
                details                 TEXT
            );
            """
        )
        self.conn.commit()

    def _seed_settings(self) -> None:
        c = self.conn.cursor()
        for key, value in DEFAULT_SETTINGS.items():
            c.execute(
                "INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                (key, value),
            )
        self.conn.commit()

    def _seed_default_subjects(self) -> None:
        c = self.conn.cursor()
        existing = c.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
        if existing:
            return
        defaults = {
            "Python": ["Tkinter", "OOP", "File Handling", "SQLite", "APIs"],
            "Mathematics": ["Algebra", "Calculus", "Geometry"],
            "English": ["Grammar", "Vocabulary", "Writing"],
            "Computer Science": ["Algorithms", "Data Structures", "OS"],
            "Physics": ["Mechanics", "Optics"],
            "Exercise": ["Cardio", "Stretching"],
        }
        for subj, topics in defaults.items():
            self.add_subject(subj, topics)

    # ---- settings ---------------------------------------------------------
    def get_settings(self) -> Dict[str, str]:
        rows = self.conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---- subjects / topics ------------------------------------------------
    def get_subjects(self) -> List[Subject]:
        rows = self.conn.execute(
            "SELECT id, name FROM subjects ORDER BY name"
        ).fetchall()
        subjects: List[Subject] = []
        for r in rows:
            topic_rows = self.conn.execute(
                "SELECT name FROM topics WHERE subject_id=? ORDER BY name",
                (r["id"],),
            ).fetchall()
            subjects.append(
                Subject(id=r["id"], name=r["name"],
                        topics=[t["name"] for t in topic_rows])
            )
        return subjects

    def get_subject_names(self) -> List[str]:
        return [s.name for s in self.get_subjects()]

    def add_subject(self, name: str, topics: Optional[List[str]] = None) -> int:
        c = self.conn.cursor()
        try:
            c.execute("INSERT INTO subjects(name) VALUES(?)", (name,))
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass
        subj_id = c.execute(
            "SELECT id FROM subjects WHERE name=?", (name,)
        ).fetchone()[0]
        for topic in (topics or []):
            try:
                c.execute(
                    "INSERT INTO topics(subject_id, name) VALUES(?, ?)",
                    (subj_id, topic),
                )
            except sqlite3.IntegrityError:
                pass
        self.conn.commit()
        return subj_id

    def delete_subject(self, name: str) -> None:
        sid = self.conn.execute(
            "SELECT id FROM subjects WHERE name=?", (name,)
        ).fetchone()
        if sid:
            self.conn.execute("DELETE FROM topics WHERE subject_id=?", (sid[0],))
            self.conn.execute("DELETE FROM subjects WHERE id=?", (sid[0],))
            self.conn.commit()

    def add_topic(self, subject_name: str, topic: str) -> None:
        sid = self.conn.execute(
            "SELECT id FROM subjects WHERE name=?", (subject_name,)
        ).fetchone()
        if not sid:
            sid = (self.add_subject(subject_name),)
        try:
            self.conn.execute(
                "INSERT INTO topics(subject_id, name) VALUES(?, ?)",
                (sid[0], topic),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass

    # ---- tasks ------------------------------------------------------------
    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"],
            date=row["date"],
            subject=row["subject"] or "",
            topic=row["topic"] or "",
            start_time=row["start_time"] or "09:00",
            duration=row["duration"] or 0,
            task_type=row["task_type"] or "Study",
            notes=row["notes"] or "",
            status=row["status"] or STATUS_UPCOMING,
            actual_working_seconds=row["actual_working_seconds"] or 0,
            total_pause_seconds=row["total_pause_seconds"] or 0,
            recurring_type=row["recurring_type"] or "Once",
            recurring_days=row["recurring_days"] or "",
        )

    def get_templates(self) -> List[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE date IS NULL ORDER BY start_time"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_tasks_for_date(self, day: str) -> List[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE date=? ORDER BY start_time", (day,)
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_task(self, task_id: int) -> Optional[Task]:
        row = self.conn.execute(
            "SELECT * FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def save_task(self, task: Task) -> int:
        c = self.conn.cursor()
        payload = (
            task.date,
            task.subject,
            task.topic,
            task.start_time,
            task.duration,
            task.task_type,
            task.notes,
            task.status,
            task.actual_working_seconds,
            task.total_pause_seconds,
            task.recurring_type,
            task.recurring_days,
        )
        if task.id is None:
            c.execute(
                "INSERT INTO tasks(date, subject, topic, start_time, duration, "
                "task_type, notes, status, actual_working_seconds, "
                "total_pause_seconds, recurring_type, recurring_days) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                payload,
            )
            task.id = c.lastrowid
        else:
            c.execute(
                "UPDATE tasks SET date=?, subject=?, topic=?, start_time=?, "
                "duration=?, task_type=?, notes=?, status=?, "
                "actual_working_seconds=?, total_pause_seconds=?, "
                "recurring_type=?, recurring_days=? WHERE id=?",
                payload + (task.id,),
            )
        self.conn.commit()
        return task.id

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def delete_tasks_for_date(self, day: str) -> None:
        self.conn.execute("DELETE FROM tasks WHERE date=?", (day,))
        self.conn.commit()

    def set_task_status(self, task_id: int, status: str,
                        working_seconds: Optional[int] = None,
                        pause_seconds: Optional[int] = None,
                        duration: Optional[int] = None) -> None:
        fields = ["status=?"]
        params: list = [status]
        if working_seconds is not None:
            fields.append("actual_working_seconds=?")
            params.append(working_seconds)
        if pause_seconds is not None:
            fields.append("total_pause_seconds=?")
            params.append(pause_seconds)
        if duration is not None:
            fields.append("duration=?")
            params.append(duration)
        params.append(task_id)
        self.conn.execute(
            f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", params
        )
        self.conn.commit()

    # ---- history ----------------------------------------------------------
    def save_summary(self, summary: DaySummary) -> None:
        self.conn.execute(
            "INSERT INTO history(date, total_planned_seconds, "
            "total_completed_seconds, tasks_total, tasks_completed, "
            "tasks_missed, completion_pct, details) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(date) DO UPDATE SET "
            "total_planned_seconds=excluded.total_planned_seconds, "
            "total_completed_seconds=excluded.total_completed_seconds, "
            "tasks_total=excluded.tasks_total, "
            "tasks_completed=excluded.tasks_completed, "
            "tasks_missed=excluded.tasks_missed, "
            "completion_pct=excluded.completion_pct, "
            "details=excluded.details",
            (
                summary.date,
                summary.total_planned_seconds,
                summary.total_completed_seconds,
                summary.tasks_total,
                summary.tasks_completed,
                summary.tasks_missed,
                summary.completion_pct,
                summary.details,
            ),
        )
        self.conn.commit()

    def get_history(self, limit: int = 60) -> List[DaySummary]:
        rows = self.conn.execute(
            "SELECT * FROM history ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            DaySummary(
                date=r["date"],
                total_planned_seconds=r["total_planned_seconds"] or 0,
                total_completed_seconds=r["total_completed_seconds"] or 0,
                tasks_total=r["tasks_total"] or 0,
                tasks_completed=r["tasks_completed"] or 0,
                tasks_missed=r["tasks_missed"] or 0,
                completion_pct=r["completion_pct"] or 0.0,
                details=r["details"] or "",
            )
            for r in rows
        ]

    def get_summary(self, day: str) -> Optional[DaySummary]:
        row = self.conn.execute(
            "SELECT * FROM history WHERE date=?", (day,)
        ).fetchone()
        if not row:
            return None
        return DaySummary(
            date=row["date"],
            total_planned_seconds=row["total_planned_seconds"] or 0,
            total_completed_seconds=row["total_completed_seconds"] or 0,
            tasks_total=row["tasks_total"] or 0,
            tasks_completed=row["tasks_completed"] or 0,
            tasks_missed=row["tasks_missed"] or 0,
            completion_pct=row["completion_pct"] or 0.0,
            details=row["details"] or "",
        )

    def close(self) -> None:
        self.conn.close()