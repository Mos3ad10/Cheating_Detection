from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, QSettings, Qt, QTimer, QUrl
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCloseEvent,
    QDesktopServices,
    QFont,
    QIcon,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
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


def _sentinel_pixmap(size: int) -> QPixmap:
    """Create the aperture-shaped Exam Sentinel mark at any display size."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scale = size / 64.0

    eye = QPainterPath()
    eye.moveTo(QPointF(8 * scale, 32 * scale))
    eye.cubicTo(
        QPointF(20 * scale, 14 * scale),
        QPointF(44 * scale, 14 * scale),
        QPointF(56 * scale, 32 * scale),
    )
    eye.cubicTo(
        QPointF(44 * scale, 50 * scale),
        QPointF(20 * scale, 50 * scale),
        QPointF(8 * scale, 32 * scale),
    )
    painter.setPen(QPen(QColor("#35d0c5"), max(1.5, 2.5 * scale)))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(eye)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor("#35d0c5")))
    painter.drawEllipse(QPointF(32 * scale, 32 * scale), 9 * scale, 9 * scale)
    painter.setBrush(QBrush(QColor("#091015")))
    painter.drawEllipse(QPointF(32 * scale, 32 * scale), 3.5 * scale, 3.5 * scale)
    painter.setBrush(QBrush(QColor("#ff6575")))
    painter.drawEllipse(QPointF(36 * scale, 28 * scale), 2 * scale, 2 * scale)
    painter.end()
    return pixmap


class VideoView(QLabel):
    def __init__(self):
        super().__init__()
        self.setObjectName("VideoView")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 420)
        self._image: QImage | None = None

    def set_frame(self, image: QImage) -> None:
        self._image = image
        self.update()

    def clear_frame(self) -> None:
        self._image = None
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#05080b"))

        if self._image is not None:
            pixmap = QPixmap.fromImage(self._image).scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - pixmap.width()) // 2
            y = (self.height() - pixmap.height()) // 2
            painter.drawPixmap(x, y, pixmap)
            painter.end()
            return

        frame = QRectF(34, 30, max(0, self.width() - 68), max(0, self.height() - 60))
        painter.setPen(QPen(QColor("#1d2a31"), 1))
        painter.drawRect(frame)

        corner = max(28.0, min(52.0, min(frame.width(), frame.height()) * 0.10))
        painter.setPen(QPen(QColor("#35d0c5"), 2))
        segments = (
            (frame.left(), frame.top(), frame.left() + corner, frame.top()),
            (frame.left(), frame.top(), frame.left(), frame.top() + corner),
            (frame.right() - corner, frame.top(), frame.right(), frame.top()),
            (frame.right(), frame.top(), frame.right(), frame.top() + corner),
            (frame.left(), frame.bottom(), frame.left() + corner, frame.bottom()),
            (frame.left(), frame.bottom() - corner, frame.left(), frame.bottom()),
            (frame.right() - corner, frame.bottom(), frame.right(), frame.bottom()),
            (frame.right(), frame.bottom() - corner, frame.right(), frame.bottom()),
        )
        for x1, y1, x2, y2 in segments:
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0 - 24.0
        painter.setPen(QPen(QColor("#24343c"), 1))
        painter.drawLine(QPointF(frame.left(), center_y), QPointF(frame.right(), center_y))
        painter.setPen(QPen(QColor("#35d0c5"), 2))
        painter.drawLine(QPointF(center_x - 18, center_y), QPointF(center_x + 18, center_y))

        mark = _sentinel_pixmap(76)
        painter.drawPixmap(int(center_x - 38), int(center_y - 96), mark)
        painter.setPen(QColor("#eaf2f5"))
        painter.setFont(QFont("Bahnschrift SemiCondensed", 16, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(0, center_y + 18, self.width(), 32),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "MONITOR STANDBY",
        )
        painter.setPen(QColor("#73838b"))
        painter.setFont(QFont("Segoe UI Variable Text", 9))
        painter.drawText(
            QRectF(0, center_y + 54, self.width(), 24),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "No exam source active",
        )
        painter.end()


class SettingsDialog(QDialog):
    def __init__(self, config: MonitorConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Detection settings")
        self.setMinimumWidth(860)

        layout = QVBoxLayout(self)
        signal_group = QGroupBox("Attention signals")
        signal_form = QFormLayout(signal_group)
        scoring_group = QGroupBox("Movement and risk")
        scoring_form = QFormLayout(scoring_group)
        self.gaze_threshold = self._spin(
            0.10, 0.90, config.gaze_threshold, "", 0.05, 2
        )
        self.gaze_alert_seconds = self._spin(
            0.5, 10.0, config.gaze_alert_seconds, " s", 0.5
        )
        self.gaze_vertical_limit = self._spin(
            0.20, 1.0, config.gaze_vertical_limit, "", 0.05, 2
        )
        self.yaw = self._spin(5.0, 45.0, config.head_yaw_threshold, " deg", 1.0)
        self.head_turn_seconds = self._spin(
            0.5, 10.0, config.head_turn_alert_seconds, " s", 0.5
        )
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
        self.body_threshold = self._spin(
            0.05, 0.50, config.body_movement_threshold, "", 0.05, 2
        )
        self.body_alert_seconds = self._spin(
            0.5, 10.0, config.body_movement_alert_seconds, " s", 0.5
        )
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
        signal_form.addRow("Side gaze threshold", self.gaze_threshold)
        signal_form.addRow("Sustained side gaze", self.gaze_alert_seconds)
        signal_form.addRow("Downward gaze filter", self.gaze_vertical_limit)
        signal_form.addRow("Head yaw", self.yaw)
        signal_form.addRow("Sustained head turn", self.head_turn_seconds)
        signal_form.addRow("Per-student calibration", self.calibration_seconds)
        signal_form.addRow("Body shift threshold", self.body_threshold)
        signal_form.addRow("Sustained body shift", self.body_alert_seconds)
        scoring_form.addRow("Movement angle", self.movement_angle)
        scoring_form.addRow("Movement window", self.movement_window)
        scoring_form.addRow("Movements to flag", self.movement_events)
        scoring_form.addRow("Risk warning", self.risk_warning)
        scoring_form.addRow("Risk alert", self.risk_alert)
        scoring_form.addRow("Risk decay", self.risk_decay)
        scoring_form.addRow("Pose-loss grace", self.pose_grace)
        scoring_form.addRow("Repeat alert cooldown", self.cooldown)

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

        columns = QHBoxLayout()
        columns.setSpacing(12)
        left_column = QVBoxLayout()
        left_column.setSpacing(10)
        left_column.addWidget(signal_group)
        left_column.addWidget(detector_group)
        right_column = QVBoxLayout()
        right_column.addWidget(scoring_group)
        right_column.addStretch()
        columns.addLayout(left_column, 1)
        columns.addLayout(right_column, 1)
        layout.addLayout(columns)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self.config.gaze_threshold = self.gaze_threshold.value()
        self.config.gaze_alert_seconds = self.gaze_alert_seconds.value()
        self.config.gaze_vertical_limit = self.gaze_vertical_limit.value()
        self.config.head_yaw_threshold = self.yaw.value()
        self.config.head_turn_alert_seconds = self.head_turn_seconds.value()
        self.config.head_calibration_seconds = self.calibration_seconds.value()
        self.config.head_movement_degrees = self.movement_angle.value()
        self.config.head_movement_window = self.movement_window.value()
        self.config.head_movement_events = self.movement_events.value()
        self.config.body_movement_threshold = self.body_threshold.value()
        self.config.body_movement_alert_seconds = self.body_alert_seconds.value()
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
        "Normal": QColor("#49d49d"),
        "Warning": QColor("#f3b85b"),
        "Suspicious": QColor("#ff6878"),
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

        self.setWindowTitle("Exam Sentinel | Exam Integrity Monitor")
        self.setWindowIcon(QIcon(_sentinel_pixmap(64)))
        self.resize(1500, 900)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._refresh_incidents()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())

        body = QWidget()
        body.setObjectName("AppBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(18, 14, 18, 10)
        body_layout.setSpacing(12)
        body_layout.addWidget(self._build_metrics())
        body_layout.addWidget(self._build_workspace(), 1)

        footer_shell = QFrame()
        footer_shell.setObjectName("Footer")
        footer = QHBoxLayout(footer_shell)
        footer.setContentsMargins(4, 0, 4, 0)
        footer.setSpacing(8)
        footer_dot = QFrame()
        footer_dot.setObjectName("FooterDot")
        footer_dot.setFixedSize(6, 6)
        footer.addWidget(footer_dot)
        self.footer_status = QLabel("Ready")
        self.footer_status.setObjectName("FooterStatus")
        footer.addWidget(self.footer_status)
        footer.addStretch()
        policy = QLabel("AI-assisted evidence | Human review required")
        policy.setObjectName("Policy")
        footer.addWidget(policy)
        body_layout.addWidget(footer_shell)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(10)

        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setPixmap(_sentinel_pixmap(44))
        mark.setFixedSize(48, 48)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(mark)

        brand_box = QVBoxLayout()
        brand_box.setSpacing(1)
        accent = QLabel("EXAM INTEGRITY OPERATIONS")
        accent.setObjectName("BrandAccent")
        brand = QLabel("Exam Sentinel")
        brand.setObjectName("Brand")
        brand_box.addWidget(accent)
        brand_box.addWidget(brand)
        layout.addLayout(brand_box)

        self.state_badge = QLabel("STANDBY")
        self.state_badge.setObjectName("StateBadge")
        self.state_badge.setProperty("state", "idle")
        layout.addWidget(self.state_badge)
        layout.addStretch()

        self.camera_button = QPushButton("Start live camera")
        self.camera_button.setProperty("primary", True)
        self.camera_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.camera_button.clicked.connect(self._start_camera)
        layout.addWidget(self.camera_button)

        self.video_button = QPushButton("Open exam video")
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

        divider = QFrame()
        divider.setObjectName("HeaderDivider")
        divider.setFrameShape(QFrame.Shape.VLine)
        layout.addWidget(divider)

        self.settings_button = QPushButton("Detection settings")
        self.settings_button.clicked.connect(self._open_settings)
        layout.addWidget(self.settings_button)
        return header

    def _build_metrics(self) -> QWidget:
        strip = QFrame()
        strip.setObjectName("MetricStrip")
        layout = QHBoxLayout(strip)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.source_value = self._add_metric(layout, "SOURCE", "Not connected", 2)
        self.students_value = self._add_metric(layout, "TRACKED STUDENTS", "0")
        self.flags_value = self._add_metric(layout, "SESSION FLAGS", "0")
        self.attention_value = self._add_metric(layout, "ATTENTION", "Clear")
        self.threshold_value = self._add_metric(
            layout,
            "SUSTAINED ALERTS",
            self._threshold_summary(),
            accent=True,
            compact=True,
            last=True,
        )
        return strip

    def _threshold_summary(self) -> str:
        return (
            f"H {self.config.head_turn_alert_seconds:.1f}  "
            f"E {self.config.gaze_alert_seconds:.1f}  "
            f"B {self.config.body_movement_alert_seconds:.1f} s"
        )

    @staticmethod
    def _add_metric(
        layout: QHBoxLayout,
        label: str,
        value: str,
        stretch: int = 1,
        accent: bool = False,
        compact: bool = False,
        last: bool = False,
    ) -> QLabel:
        cell = QFrame()
        cell.setObjectName("MetricCell")
        cell.setProperty("last", last)
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(16, 10, 16, 10)
        cell_layout.setSpacing(2)
        label_widget = QLabel(label)
        label_widget.setObjectName("MetricLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("MetricValue")
        value_widget.setProperty("accent", accent)
        value_widget.setProperty("compact", compact)
        value_widget.setMinimumWidth(90)
        cell_layout.addWidget(label_widget)
        cell_layout.addWidget(value_widget)
        layout.addWidget(cell, stretch)
        return value_widget

    def _build_workspace(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        video_shell = QFrame()
        video_shell.setObjectName("VideoShell")
        video_layout = QVBoxLayout(video_shell)
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(0)
        video_header = QFrame()
        video_header.setObjectName("PanelHeader")
        video_header.setFixedHeight(42)
        video_header_layout = QHBoxLayout(video_header)
        video_header_layout.setContentsMargins(14, 10, 14, 10)
        video_header_layout.setSpacing(10)
        video_title = QLabel("LIVE ANALYSIS")
        video_title.setObjectName("SectionTitle")
        video_header_layout.addWidget(video_title)
        video_header_layout.addStretch()
        for label, state in (
            ("Normal", "normal"),
            ("Watch", "warning"),
            ("Flagged", "alert"),
        ):
            swatch = QFrame()
            swatch.setObjectName("LegendSwatch")
            swatch.setProperty("state", state)
            swatch.setFixedSize(7, 7)
            video_header_layout.addWidget(swatch)
            legend_label = QLabel(label)
            legend_label.setObjectName("LegendLabel")
            video_header_layout.addWidget(legend_label)
        video_layout.addWidget(video_header)
        self.video_view = VideoView()
        video_layout.addWidget(self.video_view)
        splitter.addWidget(video_shell)

        side_rail = QFrame()
        side_rail.setObjectName("SideRail")
        side_rail.setMinimumWidth(390)
        side_rail.setMaximumWidth(520)
        side_layout = QVBoxLayout(side_rail)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        rail_header = QFrame()
        rail_header.setObjectName("PanelHeader")
        rail_header.setFixedHeight(42)
        rail_header_layout = QHBoxLayout(rail_header)
        rail_header_layout.setContentsMargins(14, 10, 14, 10)
        rail_title = QLabel("REVIEW DESK")
        rail_title.setObjectName("SectionTitle")
        rail_header_layout.addWidget(rail_title)
        rail_header_layout.addStretch()
        rail_hint = QLabel("HUMAN DECISION")
        rail_hint.setObjectName("RailHint")
        rail_header_layout.addWidget(rail_hint)
        side_layout.addWidget(rail_header)
        self.tabs = QTabWidget()
        self.student_table = self._build_student_table()
        incident_page = self._build_incident_page()
        self.tabs.addTab(self.student_table, "Student focus")
        self.tabs.addTab(incident_page, "Incident queue")
        side_layout.addWidget(self.tabs)
        splitter.addWidget(side_rail)
        splitter.setSizes([980, 410])
        return splitter

    def _build_student_table(self) -> QTableWidget:
        table = QTableWidget(0, 4)
        table.setObjectName("StudentTable")
        table.setHorizontalHeaderLabels(["ID", "STATE", "HEAD / EYES / BODY", "RISK"])
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
        page.setObjectName("IncidentPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        self.incident_table = QTableWidget(0, 4)
        self.incident_table.setObjectName("IncidentTable")
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
        review_actions.setSpacing(6)
        evidence_button = QPushButton("Open evidence")
        evidence_button.setProperty("primary", True)
        evidence_button.clicked.connect(self._open_evidence)
        reviewed_button = QPushButton("Mark reviewed")
        reviewed_button.setProperty("confirm", True)
        reviewed_button.clicked.connect(lambda: self._set_incident_status("Reviewed"))
        false_alarm_button = QPushButton("False alarm")
        false_alarm_button.setProperty("destructive", True)
        false_alarm_button.clicked.connect(lambda: self._set_incident_status("False alarm"))
        review_actions.addWidget(evidence_button)
        review_actions.addWidget(reviewed_button)
        review_actions.addWidget(false_alarm_button)
        layout.addLayout(review_actions)

        selection_actions = QHBoxLayout()
        selection_actions.setSpacing(6)
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
        history_actions.setSpacing(6)
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
        source_name = f"Camera {source}" if isinstance(source, int) else Path(source).name
        self.source_value.setText(source_name)
        self.source_value.setToolTip(source_name)
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
        self.start_source(0)

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
            if state.get("body_direction") in {"Left", "Right"}:
                head_state += f" | Body {state['body_direction']}"
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
                    item.setForeground(
                        self.STATUS_COLORS.get(state["status"], QColor("#eaf2f5"))
                    )
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
        self.tabs.setTabText(1, f"Incident queue ({len(incidents)})")
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
                    item.setForeground(QColor("#ff6878"))
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
                self.threshold_value.setText(self._threshold_summary())
                self.footer_status.setText("Detection settings saved")
            except ValueError as exc:
                QMessageBox.warning(self, "Invalid settings", str(exc))

    def _set_running_controls(self, running: bool) -> None:
        self.camera_button.setEnabled(not running)
        self.video_button.setEnabled(not running)
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
        self._set_state("STANDBY", "idle")
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
        if behavior_version < 6:
            settings.setValue("head_turn_alert_seconds", 1.0)
            settings.setValue("behavior_config_version", 6)
        if behavior_version < 7:
            settings.setValue("gaze_alert_seconds", 1.0)
            settings.setValue("body_movement_threshold", 0.15)
            settings.setValue("body_movement_alert_seconds", 1.0)
            settings.setValue("behavior_config_version", 7)
        return MonitorConfig(
            confidence=settings.value("confidence", 0.35, float),
            head_yaw_threshold=settings.value("head_yaw_threshold", 18.0, float),
            head_turn_alert_seconds=settings.value(
                "head_turn_alert_seconds", 1.0, float
            ),
            head_calibration_seconds=settings.value(
                "head_calibration_seconds", 2.0, float
            ),
            head_movement_degrees=settings.value("head_movement_degrees", 20.0, float),
            head_movement_window=settings.value("head_movement_window", 4.0, float),
            head_movement_events=settings.value("head_movement_events", 3, int),
            gaze_threshold=settings.value("gaze_threshold", 0.35, float),
            gaze_alert_seconds=settings.value("gaze_alert_seconds", 1.0, float),
            gaze_vertical_limit=settings.value("gaze_vertical_limit", 0.65, float),
            body_movement_threshold=settings.value(
                "body_movement_threshold", 0.15, float
            ),
            body_movement_alert_seconds=settings.value(
                "body_movement_alert_seconds", 1.0, float
            ),
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
            "head_turn_alert_seconds", self.config.head_turn_alert_seconds
        )
        settings.setValue(
            "head_calibration_seconds", self.config.head_calibration_seconds
        )
        settings.setValue("head_movement_degrees", self.config.head_movement_degrees)
        settings.setValue("head_movement_window", self.config.head_movement_window)
        settings.setValue("head_movement_events", self.config.head_movement_events)
        settings.setValue("gaze_threshold", self.config.gaze_threshold)
        settings.setValue("gaze_alert_seconds", self.config.gaze_alert_seconds)
        settings.setValue("gaze_vertical_limit", self.config.gaze_vertical_limit)
        settings.setValue(
            "body_movement_threshold", self.config.body_movement_threshold
        )
        settings.setValue(
            "body_movement_alert_seconds", self.config.body_movement_alert_seconds
        )
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
        settings.setValue("behavior_config_version", 7)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None:
            self.worker.request_stop()
            if not self.worker.wait(6000):
                event.ignore()
                QMessageBox.warning(self, "Still stopping", "The video worker is still closing.")
                return
        self.database.close()
        event.accept()
