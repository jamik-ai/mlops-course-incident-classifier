from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

MAX_PREDICTIONS = 100
MAX_NOTIFICATIONS = 200

predictions_history: deque[dict[str, Any]] = deque(maxlen=MAX_PREDICTIONS)
notifications: deque[dict[str, Any]] = deque(maxlen=MAX_NOTIFICATIONS)
_lock = threading.Lock()


def add_prediction(date: str, hourly_forecast: list[float]) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": date,
        "hourly_forecast": hourly_forecast,
    }
    with _lock:
        predictions_history.append(entry)


def get_predictions(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        entries = list(predictions_history)[-limit:]
    return reversed(entries)


def add_notification(alert_type: str, message: str, severity: str, details: dict[str, Any] | None = None) -> None:
    entry = {
        "alert_type": alert_type,
        "message": message,
        "severity": severity,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    with _lock:
        notifications.append(entry)


def get_notifications(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        entries = list(notifications)[-limit:]
    return reversed(entries)


def clear_notifications() -> None:
    with _lock:
        notifications.clear()
