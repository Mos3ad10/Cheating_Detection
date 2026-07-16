from __future__ import annotations

import time
from pathlib import Path

import cv2
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QImage

from .config import MonitorConfig
from .database import IncidentDatabase, IncidentRecorder
from .vision import ExamVisionPipeline


class MonitorWorker(QThread):
    frame_ready = pyqtSignal(QImage)
    students_ready = pyqtSignal(list)
    incident_created = pyqtSignal(dict)
    status_changed = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        source: int | str,
        config: MonitorConfig,
        project_root: Path,
        parent=None,
    ):
        super().__init__(parent)
        self.source = source
        self.config = config
        self.project_root = project_root
        self._stop_requested = False
        self._paused = False

    def request_stop(self) -> None:
        self._stop_requested = True

    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    def run(self) -> None:
        capture = None
        pipeline = None
        database = None
        try:
            self.status_changed.emit("Loading detection and face models")
            pipeline = ExamVisionPipeline(self.config, self.project_root)
            database = IncidentDatabase(self.project_root / "data" / "incidents.db")
            recorder = IncidentRecorder(database, self.project_root / "screenshots")
            capture = self._open_capture()
            if not capture.isOpened():
                raise RuntimeError(f"Could not open {self.source_label}")

            source_fps = capture.get(cv2.CAP_PROP_FPS) if isinstance(self.source, str) else 0.0
            frame_period = 1.0 / source_fps if 1.0 <= source_fps <= 60.0 else 0.0
            frame_index = 0
            self.status_changed.emit(f"Monitoring {self.source_label} on {pipeline.device_name}")

            while not self._stop_requested:
                if self._paused:
                    self.msleep(40)
                    continue
                started = time.perf_counter()
                ok, frame = capture.read()
                if not ok:
                    if isinstance(self.source, str):
                        self.status_changed.emit("Video finished")
                        break
                    self.msleep(60)
                    continue

                performance_now = time.monotonic()
                if isinstance(self.source, str) and frame_period:
                    media_time = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                    analysis_now = (
                        media_time
                        if media_time >= 0.0
                        else frame_index / source_fps
                    )
                else:
                    analysis_now = performance_now
                analysis = pipeline.process(frame, analysis_now, performance_now)
                frame_index += 1
                for trigger in analysis.triggers:
                    incident = recorder.record(
                        trigger, analysis.annotated_frame, self.source_label
                    )
                    self.incident_created.emit(incident)

                self.students_ready.emit([student.as_dict() for student in analysis.students])
                self.frame_ready.emit(self._to_qimage(analysis.annotated_frame))

                if frame_period:
                    remaining = frame_period - (time.perf_counter() - started)
                    if remaining > 0:
                        self.msleep(int(remaining * 1000))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if capture is not None:
                capture.release()
            if pipeline is not None:
                pipeline.close()
            if database is not None:
                database.close()

    @property
    def source_label(self) -> str:
        return f"Camera {self.source}" if isinstance(self.source, int) else Path(self.source).name

    def _open_capture(self):
        if isinstance(self.source, int):
            capture = cv2.VideoCapture(self.source, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                capture = cv2.VideoCapture(self.source)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
            return capture
        return cv2.VideoCapture(self.source)

    @staticmethod
    def _to_qimage(frame) -> QImage:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        return QImage(
            rgb.data,
            width,
            height,
            channels * width,
            QImage.Format.Format_RGB888,
        ).copy()
