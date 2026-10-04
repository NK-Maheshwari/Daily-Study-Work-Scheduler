# Daily Study & Work Scheduler

A complete desktop application built with **Python + Tkinter** that automatically
manages your daily study/work schedule, tracks working time per subject, plays an
alarm when the allocated time is up, and moves you to the next task.

## Features

- **Automatic scheduling** - the app continuously checks the system clock and
  activates the correct task for the current time. No manual "Start" needed.
- **System-clock based timer** - remaining time is computed as
  `end_time - now`, so it stays accurate even if the GUI is delayed.
- **Alarm system** - audible alarm (Windows `winsound` / terminal bell fallback)
  plus an in-app dialog with **Start Next / Snooze 5 / Extend +10 / Skip**.
- **Break management** - break tasks show a "BREAK TIME" card and countdown.
- **Pause / Resume / Skip / Extend / Snooze** - working time is never lost.
- **Today's schedule table** - colour-coded (green=done, blue=active,
  gray=upcoming, red=missed, orange=skipped).
- **Daily progress** - tasks completed, worked/remaining/planned time, % bar.
- **Recurring schedules** - Once / Every day / Weekdays / Weekends / Weekly
  (pick weekdays). Templates auto-expand into each new day's concrete tasks.
- **Missed-task handling** - if you launch late, fully-elapsed tasks are marked
  missed and you can reschedule them to the end of the day.
- **Data persistence** - SQLite (`data/scheduler.db`) stores tasks, subjects,
  topics, settings and daily history. State survives restarts; on relaunch the
  current task is recomputed from the clock (never reset incorrectly).
- **History** - per-day planned vs actual time, completed/missed counts, %.
- **Subject manager** - subjects with multiple topics; pick a topic per task.
- **Settings** - alarm on/off, notifications on/off, auto-start next, default
  durations, tick interval, light/dark theme.
- **End-of-day summary** - shown when all tasks are done.

## Project structure

```
daily_scheduler/
├── main.py            # entry point
├── database.py        # SQLite persistence
├── scheduler.py       # state engine + recurring expansion
├── timer.py           # system-clock timer + alarm driver
├── models.py          # Task / Subject dataclasses + helpers
├── ui/
│   ├── dashboard.py       # main window
│   ├── schedule_manager.py# CRUD screen
│   ├── history.py         # history screen
│   ├── settings.py        # settings screen
│   └── theme.py           # colours / ttk styling
└── data/                 # SQLite DB lives here (auto-created)
```

## Installing Python

1. Download Python 3.8+ from <https://www.python.org/downloads/>.
2. Run the installer and **check "Add Python to PATH"**.
3. Verify: `python --version`.

## Running the application

### Option A - using the included virtual environment (`.venv`)

A `.venv` is included. Activate it, then run:

**PowerShell:**
```powershell
cd daily_scheduler
.\.venv\Scripts\Activate.ps1
python main.py
```

**Command Prompt (cmd):**
```cmd
cd daily_scheduler
.venv\Scripts\activate.bat
python main.py
```

If PowerShell blocks the activation script, allow it once:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

You can also run directly without activating:
```powershell
.\.venv\Scripts\python.exe main.py
```

### Option B - using system Python directly

```
cd daily_scheduler
python main.py
```

Only the **Python standard library** is used (tkinter, sqlite3, winsound,
dataclasses, threading). No `pip install` is required.

## Creating today's schedule

1. Click **Schedule Manager**.
2. Fill in: Subject, Topic, Start Time (`HH:MM`), Duration (minutes), Type.
3. (Optional) Set **Recurring** to *Every day / Weekdays / Weekends / Weekly*
   and tick weekdays - the task is saved as a recurring template and also added
   to today.
4. Click **Add Task**. Repeat for each slot.
5. Close the manager - the dashboard updates automatically and the timer starts
   the correct task for the current time.

## Setting recurring tasks

In the Schedule Manager, choose a recurring option other than *Once*. The task
is stored as a template (no specific date). On any future day with no existing
schedule, templates expand automatically into that day's concrete tasks (respecting
Weekdays/Weekends/Weekly day selection).

## Using the automatic scheduler

- Just leave the app running. It checks the clock ~every 500 ms (configurable in
  Settings) and activates/advances tasks on its own.
- If **Auto-start next task** is on (default), completed tasks advance silently
  with a toast notification; otherwise the alarm dialog appears with choices.
- If you launch the app after some tasks have already passed, they are marked
  **Missed**; use *Reschedule Missed to End* in the Schedule Manager to push
  them later, or simply continue with the original schedule.

## Notes

- On Windows the alarm uses `winsound.Beep`. On Linux/macOS it falls back to the
  terminal bell.
- Closing the app while a task is active persists its working time and end time;
  reopening recomputes the correct state from the clock.