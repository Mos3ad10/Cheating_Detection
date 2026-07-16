from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from .behavior import BehaviorAnalyzer
from .config import MonitorConfig
from .domain import (
    Box,
    FrameAnalysis,
    HeadPose,
    StudentObservation,
    StudentResult,
    TrackedStudent,
)
from .head_pose import HeadPoseEstimator


class _StableIdentityTracker:
    """Maps changing detector IDs back to fixed classroom seats."""

    def __init__(self):
        self._tracks: dict[int, tuple[Box, float]] = {}
        self._raw_to_stable: dict[int, int] = {}
        self._next_id = 1

    def assign(
        self,
        box: Box,
        now: float,
        used_ids: set[int],
        raw_id: int | None,
    ) -> int:
        mapped_id = self._raw_to_stable.get(raw_id) if raw_id is not None else None
        if mapped_id is not None and mapped_id not in used_ids:
            old_box = self._tracks.get(mapped_id, (box, now))[0]
            if self._is_spatial_match(box, old_box):
                return self._remember(mapped_id, raw_id, box, now)

        candidates: list[tuple[float, int]] = []
        for stable_id, (old_box, _) in self._tracks.items():
            if stable_id in used_ids or not self._is_spatial_match(box, old_box):
                continue
            candidates.append((self._match_score(box, old_box), stable_id))
        if candidates:
            stable_id = max(candidates)[1]
            return self._remember(stable_id, raw_id, box, now)

        if raw_id is not None and raw_id > 0 and raw_id not in self._tracks:
            stable_id = raw_id
        else:
            stable_id = self._next_available_id(used_ids)
        return self._remember(stable_id, raw_id, box, now)

    def _remember(self, stable_id: int, raw_id: int | None, box: Box, now: float) -> int:
        self._tracks[stable_id] = (box, now)
        if raw_id is not None:
            self._raw_to_stable[raw_id] = stable_id
        self._next_id = max(self._next_id, stable_id + 1)
        return stable_id

    def _next_available_id(self, used_ids: set[int]) -> int:
        while self._next_id in self._tracks or self._next_id in used_ids:
            self._next_id += 1
        stable_id = self._next_id
        self._next_id += 1
        return stable_id

    @staticmethod
    def _head_anchor(box: Box) -> tuple[float, float]:
        return box.center[0], box.y1 + box.height * 0.18

    @classmethod
    def _normalized_anchor_distance(cls, first: Box, second: Box) -> float:
        first_x, first_y = cls._head_anchor(first)
        second_x, second_y = cls._head_anchor(second)
        scale = max(60.0, (first.width + second.width) / 2.0)
        return math.hypot(first_x - second_x, first_y - second_y) / scale

    @classmethod
    def _is_spatial_match(cls, first: Box, second: Box) -> bool:
        size_ratio = max(first.area, second.area) / max(1, min(first.area, second.area))
        return size_ratio <= 4.0 and (
            first.iou(second) >= 0.12
            or cls._normalized_anchor_distance(first, second) <= 0.72
        )

    @classmethod
    def _match_score(cls, first: Box, second: Box) -> float:
        distance = cls._normalized_anchor_distance(first, second)
        return first.iou(second) * 2.0 + max(0.0, 1.0 - distance)

    def expire(self, now: float, ttl: float) -> None:
        expired = {
            track_id
            for track_id, (_, seen) in self._tracks.items()
            if now - seen > ttl
        }
        for track_id in expired:
            del self._tracks[track_id]
        for raw_id in [
            key for key, stable_id in self._raw_to_stable.items() if stable_id in expired
        ]:
            del self._raw_to_stable[raw_id]


class ExamVisionPipeline:
    PERSON_CLASS = 0

    COLORS = {
        "Normal": (86, 157, 48),
        "Warning": (47, 157, 224),
        "Suspicious": (69, 71, 207),
    }

    def __init__(self, config: MonitorConfig, project_root: Path):
        self.config = config
        self.project_root = project_root
        local_model = project_root / "models" / config.detection_model
        self.model = YOLO(str(local_model if local_model.exists() else config.detection_model))
        self.device: int | str = 0 if torch.cuda.is_available() else "cpu"
        self.device_name = (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        )
        self.head_pose = HeadPoseEstimator()
        self.behavior = BehaviorAnalyzer(config)
        self._identities = _StableIdentityTracker()
        self._pose_cache: dict[int, tuple[HeadPose, float]] = {}
        self._face_box_cache: dict[
            int,
            tuple[tuple[float, float, float, float], float, str],
        ] = {}
        self._frame_number = 0
        self._frame_times: deque[float] = deque(maxlen=20)

    def process(
        self,
        frame: np.ndarray,
        now: float,
        performance_now: float | None = None,
    ) -> FrameAnalysis:
        self._identities.expire(now, self.config.stable_id_seconds)
        inference = self.model.track(
            frame,
            persist=True,
            tracker=self.config.tracker,
            classes=[self.PERSON_CLASS],
            conf=self.config.confidence,
            iou=self.config.iou_threshold,
            imgsz=self.config.image_size,
            device=self.device,
            half=self.device != "cpu",
            verbose=False,
        )[0]
        students = self._parse_detections(inference, now)
        self._refresh_head_poses(frame, students, now)

        results: list[StudentResult] = []
        triggers = []
        for student in students:
            cached_pose = self._pose_cache.get(student.track_id)
            pose = (
                cached_pose[0]
                if cached_pose and now - cached_pose[1] <= self.config.pose_cache_seconds
                else None
            )
            pose_timestamp = cached_pose[1] if pose is not None and cached_pose else None
            observation = StudentObservation(
                track_id=student.track_id,
                box=student.box,
                confidence=student.confidence,
                head_pose=pose,
                head_pose_timestamp=pose_timestamp,
            )
            result, new_triggers = self.behavior.update(observation, now)
            result.box = self._head_box(
                student,
                pose,
                now,
                frame.shape[1],
                frame.shape[0],
            )
            results.append(result)
            triggers.extend(new_triggers)

        self.behavior.expire(now)
        self._expire_pose_cache(now)
        self._expire_face_box_cache(now)
        self._frame_number += 1
        annotated = self._draw(
            frame.copy(),
            results,
            performance_now if performance_now is not None else now,
        )
        return FrameAnalysis(annotated_frame=annotated, students=results, triggers=triggers)

    def close(self) -> None:
        self.head_pose.close()

    def _parse_detections(
        self, inference, now: float
    ) -> list[TrackedStudent]:
        students: list[TrackedStudent] = []
        boxes = inference.boxes
        if boxes is None or len(boxes) == 0:
            return students

        coordinates = boxes.xyxy.int().cpu().tolist()
        class_ids = boxes.cls.int().cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        track_ids = boxes.id.int().cpu().tolist() if boxes.id is not None else [None] * len(boxes)
        people: list[tuple[Box, float, int | None]] = []
        for coords, class_id, confidence, raw_track_id in zip(
            coordinates, class_ids, confidences, track_ids
        ):
            box = Box(*coords)
            if class_id == self.PERSON_CLASS:
                people.append(
                    (
                        box,
                        float(confidence),
                        int(raw_track_id) if raw_track_id is not None else None,
                    )
                )

        used_ids: set[int] = set()
        for box, confidence, raw_track_id in self._deduplicate_people(people):
            track_id = self._identities.assign(
                box,
                now,
                used_ids,
                raw_track_id,
            )
            used_ids.add(track_id)
            students.append(TrackedStudent(track_id, box, confidence))
        return students

    @classmethod
    def _deduplicate_people(
        cls, people: list[tuple[Box, float, int | None]]
    ) -> list[tuple[Box, float, int | None]]:
        kept: list[tuple[Box, float, int | None]] = []
        for candidate in sorted(people, key=lambda item: item[1], reverse=True):
            if any(cls._duplicate_boxes(candidate[0], existing[0]) for existing in kept):
                continue
            kept.append(candidate)
        return kept

    @staticmethod
    def _duplicate_boxes(first: Box, second: Box) -> bool:
        ix1, iy1 = max(first.x1, second.x1), max(first.y1, second.y1)
        ix2, iy2 = min(first.x2, second.x2), min(first.y2, second.y2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        containment = intersection / max(1, min(first.area, second.area))
        return first.iou(second) >= 0.65 or containment >= 0.88

    def _refresh_head_poses(
        self, frame: np.ndarray, students: list[TrackedStudent], now: float
    ) -> None:
        if self._frame_number % self.config.head_pose_stride != 0:
            return
        face_hints = self._trusted_face_hints(
            students,
            now,
            frame.shape[1],
            frame.shape[0],
        )
        if self._frame_number % (self.config.head_pose_stride * 4) == 0:
            face_hints.update(
                self._refresh_detected_face_boxes(
                    frame,
                    students,
                    now,
                    face_hints,
                )
            )
        largest_students = sorted(students, key=lambda student: student.box.area, reverse=True)
        candidates: list[tuple[TrackedStudent, HeadPose]] = []
        for student in largest_students[: self.config.max_faces_per_pass]:
            pose = self.head_pose.estimate(
                frame,
                student.box,
                face_hints.get(student.track_id),
            )
            if pose is not None and pose.face_box is not None:
                candidates.append((student, pose))

        accepted, rejected_ids = self._select_unique_face_poses(candidates, face_hints)
        for track_id in rejected_ids:
            self._pose_cache.pop(track_id, None)
            cached = self._face_box_cache.get(track_id)
            if cached and cached[2] == "mesh":
                del self._face_box_cache[track_id]
        for student, pose in accepted:
            self._pose_cache[student.track_id] = (pose, now)
            source = "detector" if student.track_id in face_hints else "mesh"
            self._remember_face_box(student, pose.face_box, now, source)

    def _refresh_detected_face_boxes(
        self,
        frame: np.ndarray,
        students: list[TrackedStudent],
        now: float,
        previous_hints: dict[int, Box],
    ) -> dict[int, Box]:
        faces = self.head_pose.detect_faces(frame)
        pairs: list[tuple[float, int, int]] = []
        for face_index, face_box in enumerate(faces):
            face_x, face_y = face_box.center
            for student in students:
                expanded = student.box.expanded(0.04, frame.shape[1], frame.shape[0])
                if not expanded.contains((face_x, face_y)):
                    continue
                expected_x = student.box.center[0]
                expected_y = student.box.y1 + student.box.height * 0.18
                scale = max(50.0, student.box.width)
                body_distance = math.hypot(
                    face_x - expected_x,
                    face_y - expected_y,
                ) / scale
                size_cost = 0.18 * math.log(
                    max(1.0, student.box.area / max(1, face_box.area))
                )
                cost = body_distance + size_cost
                previous = previous_hints.get(student.track_id)
                if previous is not None:
                    previous_x, previous_y = previous.center
                    previous_scale = max(30.0, (previous.width + face_box.width) / 2.0)
                    continuity = math.hypot(
                        face_x - previous_x,
                        face_y - previous_y,
                    ) / previous_scale
                    if self._duplicate_boxes(face_box, previous):
                        cost = -2.0 + continuity
                    else:
                        cost += min(2.0, continuity) * 0.40
                pairs.append((cost, face_index, student.track_id))

        assigned: dict[int, Box] = {}
        used_faces: set[int] = set()
        for _, face_index, track_id in sorted(pairs):
            if face_index in used_faces or track_id in assigned:
                continue
            student = next(student for student in students if student.track_id == track_id)
            face_box = faces[face_index]
            assigned[track_id] = face_box
            used_faces.add(face_index)
            self._remember_face_box(student, face_box, now, "detector")
        return assigned

    @classmethod
    def _select_unique_face_poses(
        cls,
        candidates: list[tuple[TrackedStudent, HeadPose]],
        face_hints: dict[int, Box],
    ) -> tuple[list[tuple[TrackedStudent, HeadPose]], set[int]]:
        rejected: set[int] = set()
        eligible: list[tuple[int, float, TrackedStudent, HeadPose]] = []
        for student, pose in candidates:
            face_box = pose.face_box
            if face_box is None:
                continue
            belongs_to_other_hint = any(
                owner_id != student.track_id and cls._duplicate_boxes(face_box, hint)
                for owner_id, hint in face_hints.items()
            )
            if belongs_to_other_hint:
                rejected.add(student.track_id)
                continue
            own_hint = face_hints.get(student.track_id)
            hint_priority = 0 if own_hint and cls._duplicate_boxes(face_box, own_hint) else 1
            anchor_distance = _StableIdentityTracker._normalized_anchor_distance(
                student.box,
                face_box,
            )
            eligible.append((hint_priority, anchor_distance, student, pose))

        accepted: list[tuple[TrackedStudent, HeadPose]] = []
        for _, _, student, pose in sorted(
            eligible,
            key=lambda item: (item[0], item[1]),
        ):
            if any(
                cls._duplicate_boxes(pose.face_box, kept_pose.face_box)
                for _, kept_pose in accepted
                if pose.face_box is not None and kept_pose.face_box is not None
            ):
                rejected.add(student.track_id)
                continue
            accepted.append((student, pose))
        return accepted, rejected

    def _expire_pose_cache(self, now: float) -> None:
        ttl = max(self.config.pose_cache_seconds, self.config.lost_track_seconds)
        for track_id in [
            key for key, (_, timestamp) in self._pose_cache.items() if now - timestamp > ttl
        ]:
            del self._pose_cache[track_id]

    def _remember_face_box(
        self,
        student: TrackedStudent,
        face_box: Box,
        now: float,
        source: str,
    ) -> None:
        width = max(1, student.box.width)
        height = max(1, student.box.height)
        relative = (
            (face_box.x1 - student.box.x1) / width,
            (face_box.y1 - student.box.y1) / height,
            (face_box.x2 - student.box.x1) / width,
            (face_box.y2 - student.box.y1) / height,
        )
        self._face_box_cache[student.track_id] = (relative, now, source)

    def _trusted_face_hints(
        self,
        students: list[TrackedStudent],
        now: float,
        frame_width: int,
        frame_height: int,
    ) -> dict[int, Box]:
        hints: dict[int, Box] = {}
        for student in students:
            cached = self._face_box_cache.get(student.track_id)
            if (
                cached is None
                or cached[2] != "detector"
                or now - cached[1] > self.config.face_box_cache_seconds
            ):
                continue
            hints[student.track_id] = self._relative_face_box(
                student.box,
                cached[0],
                frame_width,
                frame_height,
            )
        return hints

    def _expire_face_box_cache(self, now: float) -> None:
        for track_id in [
            key
            for key, (_, timestamp, _) in self._face_box_cache.items()
            if now - timestamp > self.config.face_box_cache_seconds
        ]:
            del self._face_box_cache[track_id]

    def _head_box(
        self,
        student: TrackedStudent,
        pose: HeadPose | None,
        now: float,
        frame_width: int,
        frame_height: int,
    ) -> Box:
        if pose is not None and pose.face_box is not None and pose.face_box.area > 0:
            return pose.face_box.expanded(0.05, frame_width, frame_height)

        cached = self._face_box_cache.get(student.track_id)
        if cached and now - cached[1] <= self.config.face_box_cache_seconds:
            return self._relative_face_box(
                student.box,
                cached[0],
                frame_width,
                frame_height,
            )

        person_box = student.box
        side_padding = int(person_box.width * 0.22)
        top = person_box.y1 + int(person_box.height * 0.07)
        bottom = person_box.y1 + max(30, int(person_box.height * 0.34))
        return Box(
            max(0, person_box.x1 + side_padding),
            max(0, top),
            min(frame_width - 1, person_box.x2 - side_padding),
            min(frame_height - 1, bottom),
        )

    @staticmethod
    def _relative_face_box(
        person_box: Box,
        relative: tuple[float, float, float, float],
        frame_width: int,
        frame_height: int,
    ) -> Box:
        x1, y1, x2, y2 = relative
        return Box(
            max(0, int(person_box.x1 + x1 * person_box.width)),
            max(0, int(person_box.y1 + y1 * person_box.height)),
            min(frame_width - 1, int(person_box.x1 + x2 * person_box.width)),
            min(frame_height - 1, int(person_box.y1 + y2 * person_box.height)),
        )

    def _draw(
        self,
        frame: np.ndarray,
        students: list[StudentResult],
        now: float,
    ) -> np.ndarray:
        self._frame_times.append(now)
        fps = 0.0
        if len(self._frame_times) > 1:
            elapsed = self._frame_times[-1] - self._frame_times[0]
            fps = (len(self._frame_times) - 1) / elapsed if elapsed > 0 else 0.0

        draw_scale = max(1.0, min(1.8, frame.shape[1] / 1280.0))
        box_thickness = max(3, round(3 * draw_scale))

        for student in students:
            color = self.COLORS[student.status]
            box = student.box
            cv2.rectangle(
                frame,
                (box.x1, box.y1),
                (box.x2, box.y2),
                color,
                box_thickness,
            )
            self._student_badge(
                frame,
                student.track_id,
                student.status,
                box.x1,
                box.y1,
                color,
                draw_scale,
            )
            details = student.direction
            if student.yaw is not None:
                details += f"  {student.yaw:+.0f} deg"
            if student.gaze_direction in {"Left", "Right"}:
                details += f"  EYES {student.gaze_direction.upper()}"
            if student.movement_count:
                details += (
                    f"  HEAD CHANGE {student.movement_count}/"
                    f"{self.config.head_movement_events}"
                )
            if student.risk_score >= self.config.risk_warning_score:
                details += f"  RISK {student.risk_score:.1f}"
            self._label(
                frame,
                details,
                box.x1,
                box.y2 + round(22 * draw_scale),
                color,
                0.52 * draw_scale,
                above=False,
                thickness=max(1, round(draw_scale)),
            )

            progress_width = max(30, box.width)
            bar_y = min(frame.shape[0] - 3, box.y2 + 5)
            cv2.rectangle(
                frame,
                (box.x1, bar_y),
                (min(frame.shape[1] - 1, box.x1 + progress_width), bar_y + 4),
                (74, 82, 80),
                -1,
            )
            filled = int(progress_width * student.attention_progress)
            cv2.rectangle(
                frame,
                (box.x1, bar_y),
                (min(frame.shape[1] - 1, box.x1 + filled), bar_y + 4),
                color,
                -1,
            )

        suspicious = sum(student.status == "Suspicious" for student in students)
        banner = f"STUDENTS {len(students)}   FLAGS {suspicious}   {fps:.1f} FPS   {self.device_name}"
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 34), (18, 28, 25), -1)
        cv2.putText(
            frame,
            banner,
            (14, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (238, 244, 240),
            1,
            cv2.LINE_AA,
        )
        if not students:
            cv2.putText(
                frame,
                "No students detected",
                (max(18, frame.shape[1] // 2 - 105), frame.shape[0] // 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (220, 224, 222),
                2,
                cv2.LINE_AA,
            )
        return frame

    @staticmethod
    def _label(
        frame: np.ndarray,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
        scale: float,
        above: bool = True,
        thickness: int = 1,
    ) -> None:
        (text_width, text_height), baseline = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness
        )
        if above:
            bottom = max(text_height + baseline + 2, y)
            top = max(0, bottom - text_height - baseline - 8)
        else:
            top = max(0, min(frame.shape[0] - text_height - baseline - 8, y - text_height))
            bottom = top + text_height + baseline + 8
        right = min(frame.shape[1] - 1, x + text_width + 10)
        cv2.rectangle(frame, (x, top), (right, bottom), color, -1)
        cv2.putText(
            frame,
            text,
            (x + 5, bottom - baseline - 3),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    @staticmethod
    def _student_badge(
        frame: np.ndarray,
        track_id: int,
        status: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
        draw_scale: float,
    ) -> None:
        id_text = f"ID {track_id}"
        id_scale = 0.82 * draw_scale
        id_thickness = max(2, round(2 * draw_scale))
        status_scale = 0.48 * draw_scale
        status_thickness = max(1, round(draw_scale))
        padding_x = round(10 * draw_scale)
        padding_y = round(7 * draw_scale)

        (id_width, id_height), id_baseline = cv2.getTextSize(
            id_text, cv2.FONT_HERSHEY_DUPLEX, id_scale, id_thickness
        )
        (status_width, status_height), status_baseline = cv2.getTextSize(
            status.upper(), cv2.FONT_HERSHEY_SIMPLEX, status_scale, status_thickness
        )
        badge_height = max(
            id_height + id_baseline + 2 * padding_y,
            status_height + status_baseline + 2 * padding_y,
        )
        badge_width = id_width + status_width + 3 * padding_x
        left = max(0, min(frame.shape[1] - badge_width - 1, x))
        preferred_top = y - badge_height
        top = max(35, min(frame.shape[0] - badge_height - 1, preferred_top))
        right = left + badge_width
        bottom = top + badge_height

        cv2.rectangle(frame, (left, top), (right, bottom), (15, 22, 20), -1)
        cv2.rectangle(
            frame,
            (left, top),
            (right, bottom),
            color,
            max(2, round(2 * draw_scale)),
        )
        id_y = top + (badge_height + id_height - id_baseline) // 2
        cv2.putText(
            frame,
            id_text,
            (left + padding_x, id_y),
            cv2.FONT_HERSHEY_DUPLEX,
            id_scale,
            (255, 255, 255),
            id_thickness,
            cv2.LINE_AA,
        )
        divider_x = left + id_width + 2 * padding_x
        cv2.line(
            frame,
            (divider_x, top + padding_y),
            (divider_x, bottom - padding_y),
            color,
            max(1, round(draw_scale)),
        )
        status_y = top + (badge_height + status_height - status_baseline) // 2
        cv2.putText(
            frame,
            status.upper(),
            (divider_x + padding_x, status_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            status_scale,
            color,
            status_thickness,
            cv2.LINE_AA,
        )
