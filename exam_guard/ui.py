from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QSettings, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QCloseEvent, QDesktopServices, QImage, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStyle,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .config import MonitorConfig
from .database import IncidentDatabase
from .theme import APP_STYLESHEET
from .worker import MonitorWorker


class VideoView(QLabel):
    def __init__(self):
        super().__init__("Select a camera or open an exam video")
        self.setObjectName("VideoView")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 420)
        self._image: QImage | None = None

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self._render()

    def clear_frame(self) -> None:
        self._image = None
        self.clear()
        self.setText("Select a camera or open an exam video")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render()

    def _render(self) -> None:
        if self._image is None:
            return
        pixmap = QPixmap.fromImage(self._image).scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(pixmap)


class SettingsDialog(QDialog):
    def __init__(self, config: MonitorConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Detection settings")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        behavior_group = QGroupBox("Behavior thresholds")
        behavior_form = QFormLayout(behavior_group)
        self.gaze_threshold = self._spin(
            0.10, 0.90, config.gaze_threshold, "", 0.05, 2
        )
        self.gaze_vertical_limit = self._spin(
            0.20, 1.0, config.gaze_vertical_limit, "", 0.05, 2
        )
        self.yaw = self._spin(5.0, 45.0, config.head_yaw_threshold, " deg", 1.0)
        self.calibration_seconds = self._spin(
            0.0, 10.0, config.head_calibration_seconds, " s", 0.5
        )
        self.movement_angle = self._spin(
            5.0, 45.0, config.head_movement_degrees, " deg", 1.0
        )
        self.movement_window = self._spin(
            2.0, 15.0, config.head_movement_window, " s", 0.5
        )
        self.movement_events = QSpinBox()
        self.movement_events.setRange(2, 10)
        self.movement_events.setValue(config.head_movement_events)
        self.risk_warning = self._spin(
            0.5, 10.0, config.risk_warning_score, "", 0.5
        )
        self.risk_alert = self._spin(
            1.0, 20.0, config.risk_alert_score, "", 0.5
        )
        self.risk_decay = self._spin(
            0.1, 5.0, config.risk_decay_per_second, " /s", 0.1
        )
        self.pose_grace = self._spin(
            0.0, 3.0, config.pose_gap_grace_seconds, " s", 0.1
        )
        self.cooldown = self._spin(1.0, 120.0, config.incident_cooldown, " s", 1.0)
        behavior_form.addRow("Side gaze threshold", self.gaze_threshold)
        behavior_form.addRow("Downward gaze filter", self.gaze_vertical_limit)
        behavior_form.addRow("Head yaw", self.yaw)
        behavior_form.addRow("Per-student calibration", self.calibration_seconds)
        behavior_form.addRow("Movement angle", self.movement_angle)
        behavior_form.addRow("Movement window", self.movement_window)
        behavior_form.addRow("Movements to flag", self.movement_events)
        behavior_form.addRow("Risk warning", self.risk_warning)
        behavior_form.addRow("Risk alert", self.risk_alert)
        behavior_form.addRow("Risk decay", self.risk_decay)
        behavior_form.addRow("Pose-loss grace", self.pose_grace)
        behavior_form.addRow("Repeat alert cooldown", self.cooldown)

        detector_group = QGroupBox("Detector")
        detector_form = QFormLayout(detector_group)
        self.confidence = self._spin(0.10, 0.90, config.confidence, "", 0.05, 2)
        self.audio = QCheckBox("Sound on new incidents")
        self.audio.setChecked(config.audio_alerts)
        detector_form.addRow("Minimum confidence", self.confidence)
        detector_form.addRow("Alerts", self.audio)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(behavior_group)
        layout.addWidget(detector_group)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self.config.gaze_threshold = self.gaze_threshold.value()
        self.config.gaze_vertical_limit = self.gaze_vertical_limit.value()
        self.config.head_yaw_threshold = self.yaw.value()
        self.config.head_calibration_seconds = self.calibration_seconds.value()
        self.config.head_movement_degrees = self.movement_angle.value()
        self.config.head_movement_window = self.movement_window.value()
        self.config.head_movement_events = self.movement_events.value()
        self.config.risk_warning_score = self.risk_warning.value()
        self.config.risk_alert_score = self.risk_alert.value()
        self.config.risk_decay_per_second = self.risk_decay.value()
        self.config.pose_gap_grace_seconds = self.pose_grace.value()
        self.config.incident_cooldown = self.cooldown.value()
        self.config.confidence = self.confidence.value()
        self.config.audio_alerts = self.audio.isChecked()
        self.config.validate()

    @staticmethod
    def _spin(
        minimum: float,
        maximum: float,
        value: float,
        suffix: str,
        step: float,
        decimals: int = 1,
    ) -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(minimum, maximum)
        control.setDecimals(decimals)
        control.setSingleStep(step)
        control.setSuffix(suffix)
        control.setValue(value)
        return control


class AlertToast(QFrame):
    def __init__(self, incident: dict, parent: QWidget):
        super().__init__(parent, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        title = QLabel(f"Student {incident['track_id']} flagged")
        title.setObjectName("ToastTitle")
        body = QLabel(incident["behavior"])
        body.setObjectName("ToastBody")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        self.adjustSize()

    def show_near(self, parent: QWidget) -> None:
        self.adjustSize()
        bottom_right = parent.mapToGlobal(parent.rect().bottomRight())
        self.move(bottom_right.x() - self.width() - 24, bottom_right.y() - self.height() - 48)
        self.show()
        QTimer.singleShot(5000, self.close)


class ExamMonitorWindow(QMainWindow):
    STATUS_COLORS = {
        "Normal": QColor("#2b8a57"),
        "Warning": QColor("#b36a10"),
        "Suspicious": QColor("#c94747"),
    }

    def __init__(self, project_root: Path):
        super().__init__()
        self.project_root = project_root
        self.config = self._load_config()
        self.database = IncidentDatabase(project_root / "data" / "incidents.db")
        self.worker: MonitorWorker | None = None
        self._paused = False
        self._session_incidents = 0
        self._latest_states: list[dict] = []

        self.setWindowTitle("Exam Sentinel")
        self.resize(1460, 860)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._refresh_incidents()

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 8)
        body_layout.setSpacing(10)
        body_layout.addWidget(self._build_metrics())
        body_layout.addWidget(self._build_workspace(), 1)

        footer = QHBoxLayout()
        self.footer_status = QLabel("Ready")
        self.footer_status.setObjectName("FooterStatus")
        footer.addWidget(self.footer_status)
        body_layout.addLayout(footer)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        accent = QLabel("LIVE EXAM OPERATIONS")
        accent.setObjectName("BrandAccent")
        brand = QLabel("EXAM SENTINEL")
        brand.setObjectName("Brand")
        brand_box.addWidget(accent)
        brand_box.addWidget(brand)
        layout.addLayout(brand_box)

        self.state_badge = QLabel("IDLE")
        self.state_badge.setObjectName("StateBadge")
        self.state_badge.setProperty("state", "idle")
        layout.addWidget(self.state_badge)
        layout.addStretch()

        self.camera_select = QComboBox()
        self.camera_select.addItems([f"Camera {index}" for index in range(5)])
        self.camera_select.setFixedWidth(110)
        self.camera_button = QPushButton("Start camera")
        self.camera_button.setProperty("primary", True)
        self.camera_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.camera_button.clicked.connect(self._start_camera)
        layout.addWidget(self.camera_select)
        layout.addWidget(self.camera_button)

        self.video_button = QPushButton("Open video")
        self.video_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.video_button.clicked.connect(self._open_video)
        layout.addWidget(self.video_button)

        self.pause_button = QToolButton()
        self.pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.pause_button.setToolTip("Pause monitoring")
        self.pause_button.setEnabled(False)
        self.pause_button.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_button)

        self.stop_button = QToolButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Stop monitoring")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_monitoring)
        layout.addWidget(self.stop_button)

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)
        return header

    def _build_metrics(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("MetricStrip")
        layout = QGridLayout(strip)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setHorizontalSpacing(28)

        self.source_value = self._add_metric(layout, 0, "SOURCE", "None")
        self.students_value = self._add_metric(layout, 1, "TRACKED", "0")
        self.flags_value = self._add_metric(layout, 2, "SESSION FLAGS", "0")
        self.attention_value = self._add_metric(layout, 3, "ATTENTION", "Clear")
        layout.setColumnStretch(0, 2)
        for column in (1, 2, 3):
            layout.setColumnStretch(column, 1)
        return strip

    @staticmethod
    def _add_metric(layout: QGridLayout, column: int, label: str, value: str) -> QLabel:
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("MetricValue")
        value_widget.setMinimumWidth(100)
        layout.addWidget(label_widget, 0, column)
        layout.addWidget(value_widget, 1, column)
        return value_widget

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        video_shell = QFrame()
        video_shell.setObjectName("VideoShell")
        video_layout = QVBoxLayout(video_shell)
        video_layout.setContentsMargins(6, 6, 6, 6)
        self.video_view = VideoView()
        video_layout.addWidget(self.video_view)
        splitter.addWidget(video_shell)

        side_rail = QFrame()
        side_rail.setObjectName("SideRail")
        side_rail.setMinimumWidth(390)
        side_rail.setMaximumWidth(500)
        side_layout = QVBoxLayout(side_rail)
        side_layout.setContentsMargins(8, 8, 8, 8)
        self.tabs = QTabWidget()
        self.student_table = self._build_student_table()
        incident_page = self._build_incident_page()
        self.tabs.addTab(self.student_table, "Students")
        self.tabs.addTab(incident_page, "Incidents")
        side_layout.addWidget(self.tabs)
        splitter.addWidget(side_rail)
        splitter.setSizes([980, 410])
        return splitter

    def _build_student_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["ID", "STATE", "HEAD / EYES", "RISK"])
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        return table

    def _build_incident_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 6, 0, 0)
        self.incident_table = QTableWidget(0, 4)
        self.incident_table.setHorizontalHeaderLabels(["TIME", "STUDENT", "EVENT", "STATUS"])
        self.incident_table.setAlternatingRowColors(True)
        self.incident_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.incident_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.incident_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.incident_table.verticalHeader().setVisible(False)
        self.incident_table.doubleClicked.connect(self._open_evidence)
        header = self.incident_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.incident_table, 1)

        review_actions = QHBoxLayout()
        evidence_button = QPushButton("Open evidence")
        evidence_button.clicked.connect(self._open_evidence)
        reviewed_button = QPushButton("Mark reviewed")
        reviewed_button.clicked.connect(lambda: self._set_incident_status("Reviewed"))
        false_alarm_button = QPushButton("False alarm")
        false_alarm_button.setProperty("destructive", True)
        false_alarm_button.clicked.connect(lambda: self._set_incident_status("False alarm"))
        review_actions.addWidget(evidence_button)
        review_actions.addWidget(reviewed_button)
        review_actions.addWidget(false_alarm_button)
        layout.addLayout(review_actions)

        selection_actions = QHBoxLayout()
        folder_button = QPushButton("Evidence folder")
        folder_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        folder_button.clicked.connect(self._open_evidence_folder)
        select_all_button = QPushButton("Select all")
        select_all_button.clicked.connect(self.incident_table.selectAll)
        selection_actions.addWidget(folder_button)
        selection_actions.addWidget(select_all_button)
        layout.addLayout(selection_actions)

        history_actions = QHBoxLayout()
        delete_button = QPushButton("Delete selected")
        delete_button.setProperty("destructive", True)
        delete_button.clicked.connect(self._delete_selected_incident)
        clear_button = QPushButton("Clear history")
        clear_button.setProperty("destructive", True)
        clear_button.clicked.connect(self._clear_incident_history)
        history_actions.addWidget(delete_button)
        history_actions.addWidget(clear_button)
        layout.addLayout(history_actions)
        return page

    def start_source(self, source: int | str) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.stop_monitoring(wait=True)
        self.config.validate()
        self._paused = False
        self._session_incidents = 0
        self.flags_value.setText("0")
        self.source_value.setText(f"Camera {source}" if isinstance(source, int) else Path(source).name)
        worker = MonitorWorker(source, self.config, self.project_root, self)
        self.worker = worker
        worker.frame_ready.connect(self.video_view.set_frame)
        worker.students_ready.connect(self._update_students)
        worker.incident_created.connect(self._on_incident)
        worker.status_changed.connect(self._set_footer_status)
        worker.failed.connect(self._on_worker_error)
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()
        self._set_running_controls(True)
        self._set_state("LIVE", "live")

    def stop_monitoring(self, wait: bool = False) -> None:
        if self.worker is None:
            return
        self.worker.request_stop()
        if wait:
            self.worker.wait(5000)
        self.footer_status.setText("Stopping monitoring")

    def _start_camera(self) -> None:
        self.start_source(self.camera_select.currentIndex())

    def _open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open exam video",
            str(self.project_root),
            "Video files (*.mp4 *.avi *.mov *.mkv *.m4v);;All files (*.*)",
        )
        if path:
            self.start_source(path)

    def _toggle_pause(self) -> None:
        if self.worker is None:
            return
        self._paused = not self._paused
        self.worker.set_paused(self._paused)
        icon = QStyle.StandardPixmap.SP_MediaPlay if self._paused else QStyle.StandardPixmap.SP_MediaPause
        self.pause_button.setIcon(self.style().standardIcon(icon))
        self.pause_button.setToolTip("Resume monitoring" if self._paused else "Pause monitoring")
        self._set_state("PAUSED" if self._paused else "LIVE", "idle" if self._paused else "live")

    def _update_students(self, states: list[dict]) -> None:
        self._latest_states = states
        priority = {"Suspicious": 0, "Warning": 1, "Normal": 2}
        states = sorted(states, key=lambda item: (priority.get(item["status"], 3), item["track_id"]))
        self.student_table.setRowCount(len(states))
        for row, state in enumerate(states):
            head_state = state["direction"]
            if state.get("gaze_direction") in {"Left", "Right"}:
                head_state += f" | Eyes {state['gaze_direction']}"
            if state.get("movement_count", 0):
                head_state += (
                    f" | Changes {state['movement_count']}/"
                    f"{self.config.head_movement_events}"
                )
            values = [
                str(state["track_id"]),
                state["status"],
                head_state,
                f"{state.get('risk_score', 0.0):.1f}/{self.config.risk_alert_score:.1f}",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 1:
                    item.setForeground(self.STATUS_COLORS.get(state["status"], QColor("#18211e")))
                self.student_table.setItem(row, column, item)
        self.students_value.setText(str(len(states)))
        suspicious = sum(state["status"] == "Suspicious" for state in states)
        warnings = sum(state["status"] == "Warning" for state in states)
        if suspicious:
            self.attention_value.setText(f"{suspicious} flagged")
            self._set_state("ALERT", "alert")
        elif warnings:
            self.attention_value.setText(f"{warnings} watching")
            if not self._paused:
                self._set_state("LIVE", "live")
        else:
            self.attention_value.setText("Clear")
            if not self._paused:
                self._set_state("LIVE", "live")

    def _on_incident(self, incident: dict) -> None:
        self._session_incidents += 1
        self.flags_value.setText(str(self._session_incidents))
        self._refresh_incidents()
        self.tabs.setCurrentIndex(1)
        toast = AlertToast(incident, self)
        toast.show_near(self)
        if self.config.audio_alerts:
            QApplication.beep()

    def _refresh_incidents(self) -> None:
        incidents = self.database.list_incidents()
        self.incident_table.setRowCount(len(incidents))
        for row, incident in enumerate(incidents):
            try:
                display_time = datetime.fromisoformat(incident["occurred_at"]).strftime("%d %b %H:%M:%S")
            except ValueError:
                display_time = incident["occurred_at"]
            values = [
                display_time,
                str(incident["track_id"]),
                incident["behavior"],
                incident["status"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, incident)
                if column == 3 and value == "Needs review":
                    item.setForeground(QColor("#c94747"))
                self.incident_table.setItem(row, column, item)

    def _selected_incident(self) -> dict | None:
        incidents = self._selected_incidents()
        return incidents[0] if incidents else None

    def _selected_incidents(self) -> list[dict]:
        rows = sorted(
            index.row()
            for index in self.incident_table.selectionModel().selectedRows(0)
        )
        incidents: list[dict] = []
        for row in rows:
            item = self.incident_table.item(row, 0)
            incident = item.data(Qt.ItemDataRole.UserRole) if item else None
            if incident is not None:
                incidents.append(incident)
        return incidents

    def _open_evidence(self) -> None:
        incident = self._selected_incident()
        if incident is None:
            return
        path = Path(incident["screenshot_path"])
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.warning(self, "Evidence missing", f"Screenshot not found:\n{path}")

    def _set_incident_status(self, status: str) -> None:
        incidents = self._selected_incidents()
        if not incidents:
            return
        for incident in incidents:
            self.database.update_status(incident["id"], status)
        self._refresh_incidents()
        self.footer_status.setText(
            f"{len(incidents)} incident{'s' if len(incidents) != 1 else ''} marked {status.lower()}"
        )

    def _open_evidence_folder(self) -> None:
        folder = self.project_root / "screenshots"
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder.resolve())))

    def _delete_selected_incident(self) -> None:
        incidents = self._selected_incidents()
        if not incidents:
            return
        count = len(incidents)
        noun = "incident" if count == 1 else "incidents"
        answer = QMessageBox.question(
            self,
            f"Remove {noun} from history",
            f"Remove {count} selected {noun} from the history? Their evidence screenshots will remain saved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        for incident in incidents:
            self.database.delete_incident(incident["id"])
        self._refresh_incidents()
        self.footer_status.setText(
            f"{count} {noun} removed from history; evidence screenshots kept"
        )

    def _clear_incident_history(self) -> None:
        if self.incident_table.rowCount() == 0:
            return
        answer = QMessageBox.question(
            self,
            "Clear incident history",
            "Remove all incident records from the history? Evidence screenshots will remain saved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        screenshot_paths = self.database.clear_incidents()
        self._session_incidents = 0
        self.flags_value.setText("0")
        self._refresh_incidents()
        self.footer_status.setText(
            f"History cleared: {len(screenshot_paths)} records removed; "
            "evidence screenshots kept"
        )

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                dialog.apply()
                self._save_config()
                self.footer_status.setText("Detection settings saved")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid settings", str(exc))

    def _set_running_controls(self, running: bool) -> None:
        self.camera_button.setEnabled(not running)
        self.video_button.setEnabled(not running)
        self.camera_select.setEnabled(not running)
        self.pause_button.setEnabled(running)
        self.stop_button.setEnabled(running)
        self.settings_button.setEnabled(not running)

    def _on_worker_error(self, message: str) -> None:
        self.footer_status.setText(message)
        QMessageBox.critical(self, "Monitoring stopped", message)

    def _on_worker_finished(self, finished_worker: MonitorWorker) -> None:
        if self.worker is not finished_worker:
            finished_worker.deleteLater()
            return
        self._set_running_controls(False)
        self._set_state("IDLE", "idle")
        self.students_value.setText("0")
        self.attention_value.setText("Clear")
        self.student_table.setRowCount(0)
        self._paused = False
        self.pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.worker = None
        finished_worker.deleteLater()

    def _set_footer_status(self, message: str) -> None:
        self.footer_status.setText(message)

    def _set_state(self, text: str, state: str) -> None:
        self.state_badge.setText(text)
        self.state_badge.setProperty("state", state)
        self.state_badge.style().unpolish(self.state_badge)
        self.state_badge.style().polish(self.state_badge)

    def _load_config(self) -> MonitorConfig:
        settings = QSettings("CV Instant", "Exam Sentinel")
        behavior_version = settings.value("behavior_config_version", 1, int)
        if behavior_version < 2:
            settings.setValue("head_yaw_threshold", 18.0)
            settings.setValue("head_movement_degrees", 20.0)
            settings.setValue("head_calibration_seconds", 2.0)
            settings.setValue("behavior_config_version", 2)
        if behavior_version < 3:
            settings.setValue("gaze_threshold", 0.35)
            settings.setValue("behavior_config_version", 3)
        if behavior_version < 4:
            settings.setValue("gaze_vertical_limit", 0.65)
            settings.setValue("behavior_config_version", 4)
        if behavior_version < 5:
            settings.setValue("risk_warning_score", 2.0)
            settings.setValue("risk_alert_score", 5.0)
            settings.setValue("risk_decay_per_second", 1.25)
            settings.setValue("pose_gap_grace_seconds", 0.60)
            settings.setValue("behavior_config_version", 5)
        return MonitorConfig(
            confidence=settings.value("confidence", 0.35, float),
            head_yaw_threshold=settings.value("head_yaw_threshold", 18.0, float),
            head_calibration_seconds=settings.value(
                "head_calibration_seconds", 2.0, float
            ),
            head_movement_degrees=settings.value("head_movement_degrees", 20.0, float),
            head_movement_window=settings.value("head_movement_window", 4.0, float),
            head_movement_events=settings.value("head_movement_events", 3, int),
            gaze_threshold=settings.value("gaze_threshold", 0.35, float),
            gaze_vertical_limit=settings.value("gaze_vertical_limit", 0.65, float),
            risk_warning_score=settings.value("risk_warning_score", 2.0, float),
            risk_alert_score=settings.value("risk_alert_score", 5.0, float),
            risk_decay_per_second=settings.value(
                "risk_decay_per_second", 1.25, float
            ),
            pose_gap_grace_seconds=settings.value(
                "pose_gap_grace_seconds", 0.60, float
            ),
            incident_cooldown=settings.value("incident_cooldown", 15.0, float),
            audio_alerts=settings.value("audio_alerts", True, bool),
        )

    def _save_config(self) -> None:
        settings = QSettings("CV Instant", "Exam Sentinel")
        settings.setValue("confidence", self.config.confidence)
        settings.setValue("head_yaw_threshold", self.config.head_yaw_threshold)
        settings.setValue(
            "head_calibration_seconds", self.config.head_calibration_seconds
        )
        settings.setValue("head_movement_degrees", self.config.head_movement_degrees)
        settings.setValue("head_movement_window", self.config.head_movement_window)
        settings.setValue("head_movement_events", self.config.head_movement_events)
        settings.setValue("gaze_threshold", self.config.gaze_threshold)
        settings.setValue("gaze_vertical_limit", self.config.gaze_vertical_limit)
        settings.setValue("risk_warning_score", self.config.risk_warning_score)
        settings.setValue("risk_alert_score", self.config.risk_alert_score)
        settings.setValue(
            "risk_decay_per_second", self.config.risk_decay_per_second
        )
        settings.setValue(
            "pose_gap_grace_seconds", self.config.pose_gap_grace_seconds
        )
        settings.setValue("incident_cooldown", self.config.incident_cooldown)
        settings.setValue("audio_alerts", self.config.audio_alerts)
        settings.setValue("behavior_config_version", 5)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            if not self.worker.wait(6000):
                event.ignore()
                QMessageBox.warning(self, "Still stopping", "The video worker is still closing.")
                return
        self.database.close()
        event.accept()
