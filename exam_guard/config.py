from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MonitorConfig:
    detection_model: str = "yolo11n.pt"
    tracker: str = "botsort.yaml"
    confidence: float = 0.35
    iou_threshold: float = 0.50
    image_size: int = 640
    head_yaw_threshold: float = 18.0
    head_alert_yaw_threshold: float = 35.0
    head_calibration_seconds: float = 2.0
    head_movement_degrees: float = 20.0
    head_movement_window: float = 4.0
    head_movement_events: int = 3
    head_movement_refractory: float = 0.75
    gaze_threshold: float = 0.35
    gaze_vertical_limit: float = 0.65
    risk_warning_score: float = 2.0
    risk_alert_score: float = 5.0
    risk_decay_per_second: float = 1.25
    pose_gap_grace_seconds: float = 0.60
    incident_cooldown: float = 15.0
    alert_hold_seconds: float = 5.0
    head_pose_stride: int = 3
    max_faces_per_pass: int = 12
    pose_cache_seconds: float = 0.8
    lost_track_seconds: float = 2.0
    stable_id_seconds: float = 8.0
    face_box_cache_seconds: float = 4.0
    camera_width: int = 1280
    camera_height: int = 720
    audio_alerts: bool = True

    def validate(self) -> None:
        if not 0.05 <= self.confidence <= 0.95:
            raise ValueError("Detection confidence must be between 0.05 and 0.95")
        if not 5.0 <= self.head_yaw_threshold <= 45.0:
            raise ValueError("Head yaw threshold must be between 5 and 45 degrees")
        if not 15.0 <= self.head_alert_yaw_threshold <= 60.0:
            raise ValueError("Head alert angle must be between 15 and 60 degrees")
        if not 0.0 <= self.head_calibration_seconds <= 10.0:
            raise ValueError("Head calibration time must be between 0 and 10 seconds")
        if not 5.0 <= self.head_movement_degrees <= 45.0:
            raise ValueError("Head movement angle must be between 5 and 45 degrees")
        if not 2.0 <= self.head_movement_window <= 15.0:
            raise ValueError("Head movement window must be between 2 and 15 seconds")
        if not 2 <= self.head_movement_events <= 10:
            raise ValueError("Head movement event count must be between 2 and 10")
        if not 0.10 <= self.gaze_threshold <= 0.90:
            raise ValueError("Eye-gaze threshold must be between 0.10 and 0.90")
        if not 0.20 <= self.gaze_vertical_limit <= 1.0:
            raise ValueError("Vertical eye-gaze limit must be between 0.20 and 1.0")
        if not 0.5 <= self.risk_warning_score <= 10.0:
            raise ValueError("Risk warning score must be between 0.5 and 10")
        if not self.risk_warning_score < self.risk_alert_score <= 20.0:
            raise ValueError("Risk alert score must be above warning and at most 20")
        if not 0.1 <= self.risk_decay_per_second <= 5.0:
            raise ValueError("Risk decay must be between 0.1 and 5 per second")
        if not 0.0 <= self.pose_gap_grace_seconds <= 3.0:
            raise ValueError("Pose gap grace must be between 0 and 3 seconds")
        if self.incident_cooldown < 1.0:
            raise ValueError("Incident cooldown must be at least one second")
        if not 1.0 <= self.alert_hold_seconds <= 30.0:
            raise ValueError("Alert hold time must be between 1 and 30 seconds")
