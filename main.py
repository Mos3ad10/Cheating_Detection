from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from exam_guard.ui import ExamMonitorWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Exam Sentinel desktop monitor")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--camera", type=int, help="Open a camera index at startup")
    source.add_argument("--video", type=str, help="Open a video file at startup")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parent
    os.chdir(project_root)

    app = QApplication(sys.argv)
    app.setApplicationName("Exam Sentinel")
    app.setOrganizationName("CV Instant")
    window = ExamMonitorWindow(project_root)
    window.show()

    if args.camera is not None:
        QTimer.singleShot(0, lambda: window.start_source(args.camera))
    elif args.video:
        video_path = str(Path(args.video).expanduser().resolve())
        QTimer.singleShot(0, lambda: window.start_source(video_path))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
