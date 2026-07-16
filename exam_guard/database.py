from __future__ import annotations

import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

import cv2

from .domain import IncidentTrigger


class IncidentDatabase:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._lock = threading.Lock()
        self._connection = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at TEXT NOT NULL,
                    track_id INTEGER NOT NULL,
                    behavior TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    screenshot_path TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Needs review',
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def add_incident(
        self,
        occurred_at: str,
        track_id: int,
        behavior: str,
        confidence: float,
        screenshot_path: str,
        source: str,
    ) -> dict:
        with self._lock, self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO incidents
                    (occurred_at, track_id, behavior, confidence, screenshot_path, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (occurred_at, track_id, behavior, confidence, screenshot_path, source),
            )
            row = self._connection.execute(
                "SELECT * FROM incidents WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return dict(row)

    def list_incidents(self, limit: int = 250) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM incidents ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]

    def update_status(self, incident_id: int, status: str) -> None:
        if status not in {"Needs review", "Reviewed", "False alarm"}:
            raise ValueError(f"Unsupported incident status: {status}")
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE incidents SET status = ? WHERE id = ?", (status, incident_id)
            )

    def delete_incident(self, incident_id: int) -> str | None:
        with self._lock, self._connection:
            row = self._connection.execute(
                "SELECT screenshot_path FROM incidents WHERE id = ?", (incident_id,)
            ).fetchone()
            if row is None:
                return None
            self._connection.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        return str(row["screenshot_path"])

    def clear_incidents(self) -> list[str]:
        with self._lock, self._connection:
            rows = self._connection.execute(
                "SELECT screenshot_path FROM incidents"
            ).fetchall()
            self._connection.execute("DELETE FROM incidents")
        return [str(row["screenshot_path"]) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class IncidentRecorder:
    def __init__(self, database: IncidentDatabase, screenshot_dir: Path):
        self.database = database
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    def record(self, trigger: IncidentTrigger, frame, source: str) -> dict:
        now = datetime.now().astimezone()
        safe_behavior = re.sub(r"[^a-z0-9]+", "_", trigger.behavior.lower()).strip("_")
        filename = (
            f"incident_{now:%Y%m%d_%H%M%S_%f}_student_{trigger.track_id}_{safe_behavior}.jpg"
        )
        screenshot_path = self.screenshot_dir / filename
        if not cv2.imwrite(str(screenshot_path), frame):
            raise OSError(f"Could not save incident screenshot: {screenshot_path}")
        return self.database.add_incident(
            occurred_at=now.isoformat(timespec="seconds"),
            track_id=trigger.track_id,
            behavior=trigger.label,
            confidence=trigger.confidence,
            screenshot_path=str(screenshot_path.resolve()),
            source=source,
        )
