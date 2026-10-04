"""Entry point for the Daily Study & Work Scheduler.

Run with:  python main.py
"""
from __future__ import annotations

import os
import sys

# Ensure the project directory is importable regardless of CWD.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from database import Database
from ui.dashboard import Dashboard


def main() -> None:
    db_path = os.path.join(_HERE, "data", "scheduler.db")
    db = Database(db_path)
    app = Dashboard(db)
    app.mainloop()
    db.close()


if __name__ == "__main__":
    main()