"""System-clock based timer + alarm driver.

The timer never decrements a counter.  On every tick it asks the scheduler for
the current state (computed from ``datetime.now()``) and refreshes the UI.
When the active task's remaining time reaches zero it fires the alarm.
"""
from __future__ import annotations

import platform
import threading
from datetime import datetime
from typing import Callable, Optional

try:
    import winsound  # Windows only (standard library)
    _HAS_WINSOUND = True
except Exception:  # pragma: no cover - non-Windows
    _HAS_WINSOUND = False


class Timer:
    def __init__(self, root, scheduler, on_tick: Callable[[], None],
                 on_alarm: Callable, interval_ms: int = 500):
        self.root = root
        self.scheduler = scheduler
        self.on_tick = on_tick
        self.on_alarm = on_alarm
        self.interval_ms = interval_ms
        self.running = False
        self._alarm_active = False

    # ---- loop -------------------------------------------------------------
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._schedule_tick()

    def stop(self) -> None:
        self.running = False

    def set_interval(self, ms: int) -> None:
        self.interval_ms = max(100, min(ms, 2000))

    def _schedule_tick(self) -> None:
        if not self.running:
            return
        self.root.after(self.interval_ms, self._tick)

    def _tick(self) -> None:
        if not self.running:
            return
        try:
            self.on_tick()
        except Exception:
            pass
        self._schedule_tick()

    # ---- alarm sound ------------------------------------------------------
    @staticmethod
    def play_alarm(repeat: int = 3) -> None:
        """Play an audible alarm using only the standard library."""
        def _beep():
            if _HAS_WINSOUND:
                for _ in range(repeat):
                    try:
                        winsound.Beep(880, 400)
                        winsound.Beep(660, 300)
                    except Exception:
                        break
            else:
                # Fallback: terminal bell + a short busy loop is not ideal;
                # use the ASCII bell on the current stdout.
                for _ in range(repeat):
                    print("\a", end="", flush=True)

        threading.Thread(target=_beep, daemon=True).start()

    @staticmethod
    def play_start_chime() -> None:
        def _chime():
            if _HAS_WINSOUND:
                try:
                    winsound.Beep(1000, 200)
                except Exception:
                    pass
            else:
                print("\a", end="", flush=True)

        threading.Thread(target=_chime, daemon=True).start()