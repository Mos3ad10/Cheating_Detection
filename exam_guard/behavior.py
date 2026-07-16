from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Optional

from .config import MonitorConfig
from .domain import IncidentTrigger, StudentObservation, StudentResult


@dataclass(slots=True)
class _TrackState:
    last_seen: float
    direction: str = "Unknown"
    smoothed_yaw: Optional[float] = None
    smoothed_pitch: Optional[float] = None
    look_started: Optional[float] = None
    calibration_started: Optional[float] = None
    calibration_yaws: deque[float] = field(default_factory=deque)
    calibration_pitches: deque[float] = field(default_factory=deque)
    calibration_gazes: deque[float] = field(default_factory=deque)
    baseline_yaw: Optional[float] = None
    baseline_pitch: Optional[float] = None
    baseline_gaze: Optional[float] = None
    yaw_history: deque[float] = field(default_factory=lambda: deque(maxlen=3))
    pitch_history: deque[float] = field(default_factory=lambda: deque(maxlen=3))
    last_filtered_yaw: Optional[float] = None
    last_filtered_pitch: Optional[float] = None
    last_pose_timestamp: Optional[float] = None
    last_movement_time: float = float("-inf")
    last_movement_side: str = ""
    movement_events: deque[float] = field(default_factory=deque)
    movement_label: str = ""
    gaze_history: deque[float] = field(default_factory=lambda: deque(maxlen=3))
    smoothed_gaze: Optional[float] = None
    gaze_direction: str = "Center"
    gaze_started: Optional[float] = None
    active_alerts: set[str] = field(default_factory=set)
    last_incident: float = float("-inf")
    suspicious_until: float = float("-inf")
    risk_score: float = 0.0
    risk_updated_at: Optional[float] = None
    last_pose_available: float = float("-inf")


class BehaviorAnalyzer:
    """Turns calibrated per-student observations into reviewable behavior flags."""

    def __init__(self, config: MonitorConfig):
        self.config = config
        self._tracks: dict[int, _TrackState] = {}

    def update(
        self, observation: StudentObservation, now: float
    ) -> tuple[StudentResult, list[IncidentTrigger]]:
        state = self._tracks.setdefault(observation.track_id, _TrackState(last_seen=now))
        state.last_seen = now
        if observation.head_pose is not None:
            state.last_pose_available = now

        direction, movement_count, pose_ready = self._update_pose_state(
            state, observation, now
        )
        look_seconds = now - state.look_started if state.look_started is not None else 0.0
        gaze_seconds = now - state.gaze_started if state.gaze_started is not None else 0.0
        risk_reason, risk_behavior, qualifying_evidence = self._update_dynamic_risk(
            state,
            observation,
            direction,
            movement_count,
            pose_ready,
            now,
        )
        attention_progress = min(
            1.0,
            state.risk_score / self.config.risk_alert_score,
        )

        active_alerts: list[tuple[str, str, float]] = []
        if (
            state.risk_score >= self.config.risk_alert_score
            and qualifying_evidence
            and risk_behavior
        ):
            label = (
                f"{risk_reason} (risk {state.risk_score:.1f}/"
                f"{self.config.risk_alert_score:.1f})"
            )
            active_alerts.append(
                (
                    risk_behavior,
                    label,
                    state.risk_score / self.config.risk_alert_score,
                )
            )

        if active_alerts:
            status = "Suspicious"
            reasons = [active_alerts[0][1]]
            state.suspicious_until = max(
                state.suspicious_until,
                now + self.config.alert_hold_seconds,
            )
        elif now < state.suspicious_until:
            status = "Suspicious"
            reasons = ["Recent suspicious behavior under review"]
        elif state.risk_score >= self.config.risk_warning_score:
            status = "Warning"
            reasons = [
                f"{risk_reason or 'Head/eye evidence'} building "
                f"({state.risk_score:.1f}/{self.config.risk_alert_score:.1f})"
            ]
        else:
            status = "Normal"
            reasons = []

        triggers: list[IncidentTrigger] = []
        active_behaviors = {behavior for behavior, _, _ in active_alerts}
        newly_active = [
            alert for alert in active_alerts if alert[0] not in state.active_alerts
        ]
        state.active_alerts = active_behaviors
        if newly_active and now - state.last_incident >= self.config.incident_cooldown:
            priority = {
                "head_eye_risk": 4,
                "side_gaze": 3,
                "sustained_head_turn": 2,
                "repeated_head_movement": 1,
            }
            behavior, label, score = max(
                newly_active,
                key=lambda alert: priority.get(alert[0], 0),
            )
            state.last_incident = now
            triggers.append(
                IncidentTrigger(
                    track_id=observation.track_id,
                    behavior=behavior,
                    label=label,
                    confidence=min(1.0, observation.confidence * min(score, 1.0)),
                    box=observation.box,
                )
            )

        result = StudentResult(
            track_id=observation.track_id,
            box=observation.box,
            confidence=observation.confidence,
            status=status,
            direction=direction,
            yaw=state.smoothed_yaw,
            look_seconds=look_seconds,
            gaze_direction=state.gaze_direction,
            gaze_seconds=gaze_seconds,
            gaze_horizontal=state.smoothed_gaze,
            movement_count=movement_count,
            movement_label=state.movement_label,
            reason="; ".join(reasons),
            risk_score=state.risk_score,
            attention_progress=attention_progress,
        )
        return result, triggers

    def _update_dynamic_risk(
        self,
        state: _TrackState,
        observation: StudentObservation,
        direction: str,
        movement_count: int,
        pose_ready: bool,
        now: float,
    ) -> tuple[str, str, bool]:
        previous_update = state.risk_updated_at
        state.risk_updated_at = now
        if previous_update is None:
            return "", "", False
        elapsed = max(0.0, min(0.5, now - previous_update))

        pose_recent = (
            pose_ready
            or now - state.last_pose_available <= self.config.pose_gap_grace_seconds
        )
        yaw = abs(state.smoothed_yaw or 0.0)
        head_side = pose_recent and direction in {"Left", "Right"}
        gaze_side = pose_recent and state.gaze_direction in {"Left", "Right"}

        head_rate = 0.0
        if head_side and yaw >= self.config.head_yaw_threshold:
            span = max(
                1.0,
                self.config.head_alert_yaw_threshold - self.config.head_yaw_threshold,
            )
            intensity = min(
                1.0,
                max(0.0, (yaw - self.config.head_yaw_threshold) / span),
            )
            head_rate = 0.25 + 0.85 * intensity
            if yaw >= self.config.head_alert_yaw_threshold:
                head_rate += 0.20 * min(
                    1.0,
                    (yaw - self.config.head_alert_yaw_threshold) / 20.0,
                )

        gaze_rate = 0.0
        gaze_value = abs(state.smoothed_gaze or 0.0)
        if gaze_side and gaze_value >= self.config.gaze_threshold:
            gaze_span = max(0.05, 1.0 - self.config.gaze_threshold)
            gaze_intensity = min(
                1.0,
                max(0.0, (gaze_value - self.config.gaze_threshold) / gaze_span),
            )
            gaze_rate = 0.75 + gaze_intensity

        same_side = head_side and gaze_side and direction == state.gaze_direction
        opposite_side = head_side and gaze_side and direction != state.gaze_direction
        if opposite_side:
            gaze_rate *= 0.25

        evidence_rate = head_rate + gaze_rate
        if same_side:
            evidence_rate *= 1.35
        evidence_rate *= 0.75 + 0.25 * observation.confidence

        if movement_count >= self.config.head_movement_events:
            state.risk_score = max(
                state.risk_score,
                self.config.risk_alert_score,
            )

        if evidence_rate > 0.0:
            state.risk_score = min(
                self.config.risk_alert_score * 1.5,
                state.risk_score + evidence_rate * elapsed,
            )
        else:
            state.risk_score = max(
                0.0,
                state.risk_score - self.config.risk_decay_per_second * elapsed,
            )

        strong_head = head_side and yaw >= self.config.head_alert_yaw_threshold
        qualifying = strong_head or gaze_side or movement_count >= self.config.head_movement_events
        if movement_count >= self.config.head_movement_events:
            return "Repeated head movement", "repeated_head_movement", True
        if same_side:
            return f"Head and eyes looking {direction.lower()}", "head_eye_risk", True
        if gaze_side:
            return f"Eyes looking {state.gaze_direction.lower()}", "side_gaze", True
        if strong_head:
            return f"Strong head turn {direction.lower()}", "sustained_head_turn", True
        if head_side:
            return f"Head turn {direction.lower()}", "", qualifying
        return "", "", qualifying

    def expire(self, now: float) -> None:
        expired = [
            track_id
            for track_id, state in self._tracks.items()
            if now - state.last_seen > self.config.lost_track_seconds
        ]
        for track_id in expired:
            del self._tracks[track_id]

    def _update_pose_state(
        self, state: _TrackState, observation: StudentObservation, now: float
    ) -> tuple[str, int, bool]:
        cutoff = now - self.config.head_movement_window
        while state.movement_events and state.movement_events[0] < cutoff:
            state.movement_events.popleft()
        if now - state.last_movement_time > 1.0:
            state.movement_label = ""

        pose = observation.head_pose
        if pose is None:
            if now - state.last_pose_available <= self.config.pose_gap_grace_seconds:
                return (
                    state.direction,
                    len(state.movement_events),
                    state.baseline_yaw is not None,
                )
            state.direction = "Unknown"
            state.look_started = None
            state.gaze_direction = "Center"
            state.gaze_started = None
            return state.direction, len(state.movement_events), False

        measurement_time = observation.head_pose_timestamp
        if measurement_time is None:
            measurement_time = now
        if state.last_pose_timestamp == measurement_time:
            return state.direction, len(state.movement_events), state.baseline_yaw is not None

        previous_pose_timestamp = state.last_pose_timestamp
        state.last_pose_timestamp = measurement_time
        if state.baseline_yaw is None or state.baseline_pitch is None:
            return self._calibrate_pose(
                state,
                pose.yaw,
                pose.pitch,
                pose.gaze_horizontal,
                measurement_time,
            )

        relative_yaw = pose.yaw - state.baseline_yaw
        relative_pitch = pose.pitch - state.baseline_pitch
        state.yaw_history.append(relative_yaw)
        state.pitch_history.append(relative_pitch)
        filtered_yaw = float(median(state.yaw_history))
        filtered_pitch = float(median(state.pitch_history))
        state.smoothed_yaw = filtered_yaw
        state.smoothed_pitch = filtered_pitch

        continuous = (
            previous_pose_timestamp is not None
            and measurement_time - previous_pose_timestamp
            <= self.config.pose_cache_seconds * 2.5
        )
        outside_refractory = (
            now - state.last_movement_time >= self.config.head_movement_refractory
        )
        movement_side = self._direction_from_relative_yaw(filtered_yaw)
        if (
            continuous
            and outside_refractory
            and state.last_filtered_yaw is not None
            and movement_side in {"Left", "Right"}
            and movement_side != state.last_movement_side
        ):
            yaw_change = filtered_yaw - state.last_filtered_yaw
            if abs(yaw_change) >= self.config.head_movement_degrees:
                state.movement_label = f"Turned {movement_side.lower()}"
                state.movement_events.append(now)
                state.last_movement_time = now
                state.last_movement_side = movement_side

        state.last_filtered_yaw = filtered_yaw
        state.last_filtered_pitch = filtered_pitch
        self._update_gaze_state(
            state,
            pose.gaze_horizontal,
            pose.gaze_vertical,
            measurement_time,
        )
        direction = self._direction_from_relative_yaw(filtered_yaw)
        if direction in {"Left", "Right"}:
            if state.look_started is None or state.direction != direction:
                state.look_started = now
        else:
            state.look_started = None
        state.direction = direction
        return direction, len(state.movement_events), True

    def _calibrate_pose(
        self,
        state: _TrackState,
        yaw: float,
        pitch: float,
        gaze: Optional[float],
        measurement_time: float,
    ) -> tuple[str, int, bool]:
        if state.calibration_started is None:
            state.calibration_started = measurement_time
        state.calibration_yaws.append(yaw)
        state.calibration_pitches.append(pitch)
        if gaze is not None:
            state.calibration_gazes.append(gaze)
        minimum_samples = 1 if self.config.head_calibration_seconds == 0 else 3
        elapsed = measurement_time - state.calibration_started
        if elapsed < self.config.head_calibration_seconds or len(state.calibration_yaws) < minimum_samples:
            state.direction = "Calibrating"
            state.look_started = None
            state.smoothed_yaw = None
            return state.direction, len(state.movement_events), False

        state.baseline_yaw = float(median(state.calibration_yaws))
        state.baseline_pitch = float(median(state.calibration_pitches))
        if state.calibration_gazes:
            state.baseline_gaze = float(median(state.calibration_gazes))
        state.yaw_history.extend((0.0, 0.0, 0.0))
        state.pitch_history.extend((0.0, 0.0, 0.0))
        state.gaze_history.extend((0.0, 0.0, 0.0))
        state.last_filtered_yaw = 0.0
        state.last_filtered_pitch = 0.0
        state.smoothed_yaw = 0.0
        state.smoothed_pitch = 0.0
        state.smoothed_gaze = 0.0 if state.baseline_gaze is not None else None
        state.direction = "Forward"
        state.look_started = None
        state.gaze_direction = "Center"
        state.gaze_started = None
        return state.direction, len(state.movement_events), True

    def _update_gaze_state(
        self,
        state: _TrackState,
        gaze: Optional[float],
        vertical_gaze: Optional[float],
        measurement_time: float,
    ) -> None:
        if (
            gaze is None
            or vertical_gaze is None
            or abs(vertical_gaze) > self.config.gaze_vertical_limit
        ):
            state.gaze_direction = "Center"
            state.gaze_started = None
            state.smoothed_gaze = None
            return
        if state.baseline_gaze is None:
            state.baseline_gaze = gaze
            state.gaze_history.extend((0.0, 0.0, 0.0))

        state.gaze_history.append(gaze - state.baseline_gaze)
        filtered_gaze = float(median(state.gaze_history))
        state.smoothed_gaze = filtered_gaze
        if abs(filtered_gaze) < self.config.gaze_threshold:
            state.gaze_direction = "Center"
            state.gaze_started = None
            return

        direction = "Right" if filtered_gaze > 0 else "Left"
        if state.gaze_started is None or direction != state.gaze_direction:
            state.gaze_started = measurement_time
        state.gaze_direction = direction

    def _direction_from_relative_yaw(self, yaw: float) -> str:
        if yaw <= -self.config.head_yaw_threshold:
            return "Left"
        if yaw >= self.config.head_yaw_threshold:
            return "Right"
        return "Forward"
