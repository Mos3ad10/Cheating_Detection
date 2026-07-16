from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class Box:
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def contains(self, point: tuple[float, float]) -> bool:
        x, y = point
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2

    def expanded(self, ratio: float, frame_width: int, frame_height: int) -> "Box":
        dx = int(self.width * ratio)
        dy = int(self.height * ratio)
        return Box(
            max(0, self.x1 - dx),
            max(0, self.y1 - dy),
            min(frame_width - 1, self.x2 + dx),
            min(frame_height - 1, self.y2 + dy),
        )

    def iou(self, other: "Box") -> float:
        ix1, iy1 = max(self.x1, other.x1), max(self.y1, other.y1)
        ix2, iy2 = min(self.x2, other.x2), min(self.y2, other.y2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        union = self.area + other.area - intersection
        return intersection / union if union else 0.0


@dataclass(frozen=True, slots=True)
class TrackedStudent:
    track_id: int
    box: Box
    confidence: float


@dataclass(frozen=True, slots=True)
class HeadPose:
    yaw: float
    pitch: float
    roll: float
    face_box: Optional[Box] = None
    gaze_horizontal: Optional[float] = None
    gaze_vertical: Optional[float] = None


@dataclass(frozen=True, slots=True)
class StudentObservation:
    track_id: int
    box: Box
    confidence: float
    head_pose: Optional[HeadPose]
    head_pose_timestamp: Optional[float] = None


@dataclass(slots=True)
class StudentResult:
    track_id: int
    box: Box
    confidence: float
    status: str
    direction: str
    yaw: Optional[float]
    look_seconds: float
    gaze_direction: str
    gaze_seconds: float
    gaze_horizontal: Optional[float]
    movement_count: int
    movement_label: str
    reason: str
    risk_score: float
    attention_progress: float

    def as_dict(self) -> dict:
        return {
            "track_id": self.track_id,
            "status": self.status,
            "direction": self.direction,
            "yaw": self.yaw,
            "look_seconds": self.look_seconds,
            "gaze_direction": self.gaze_direction,
            "gaze_seconds": self.gaze_seconds,
            "gaze_horizontal": self.gaze_horizontal,
            "movement_count": self.movement_count,
            "movement_label": self.movement_label,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "attention_progress": self.attention_progress,
        }


@dataclass(frozen=True, slots=True)
class IncidentTrigger:
    track_id: int
    behavior: str
    label: str
    confidence: float
    box: Box


@dataclass(slots=True)
class FrameAnalysis:
    annotated_frame: object
    students: list[StudentResult] = field(default_factory=list)
    triggers: list[IncidentTrigger] = field(default_factory=list)
