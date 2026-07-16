from __future__ import annotations

import math

import cv2
import numpy as np

from .domain import Box, HeadPose


class HeadPoseEstimator:
    """Estimates stable face geometry and gaze inside each student crop."""

    RIGHT_EYE_CORNERS = (33, 133)
    LEFT_EYE_CORNERS = (362, 263)
    RIGHT_EYE_LIDS = (159, 145)
    LEFT_EYE_LIDS = (386, 374)
    RIGHT_IRIS_CENTER = 468
    LEFT_IRIS_CENTER = 473

    def __init__(self):
        import mediapipe as mp

        self._mesh = mp.solutions.face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.50,
        )
        self._detector = mp.solutions.face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.35,
        )

    def estimate(
        self,
        frame: np.ndarray,
        student_box: Box,
        face_hint: Box | None = None,
    ) -> HeadPose | None:
        frame_height, frame_width = frame.shape[:2]
        if face_hint is not None:
            pad_x = int(face_hint.width * 0.45)
            pad_top = int(face_hint.height * 0.55)
            pad_bottom = int(face_hint.height * 0.35)
            x1 = max(0, face_hint.x1 - pad_x)
            x2 = min(frame_width, face_hint.x2 + pad_x)
            y1 = max(0, face_hint.y1 - pad_top)
            y2 = min(frame_height, face_hint.y2 + pad_bottom)
        else:
            pad_x = int(student_box.width * 0.08)
            pad_y = int(student_box.height * 0.05)
            x1 = max(0, student_box.x1 - pad_x)
            x2 = min(frame_width, student_box.x2 + pad_x)
            y1 = max(0, student_box.y1 - pad_y)
            y2 = min(frame_height, student_box.y1 + int(student_box.height * 0.62))
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0 or crop.shape[0] < 32 or crop.shape[1] < 32:
            return None

        crop = self._resize_for_face_mesh(crop)
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return None

        landmarks = result.multi_face_landmarks[0].landmark
        yaw, pitch, roll = self._estimate_angles(landmarks)
        face_box = self._face_box(
            landmarks,
            x1,
            y1,
            x2 - x1,
            y2 - y1,
            frame_width,
            frame_height,
        )
        gaze_horizontal, gaze_vertical = self._estimate_gaze(landmarks)
        return HeadPose(
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            face_box=face_box,
            gaze_horizontal=gaze_horizontal,
            gaze_vertical=gaze_vertical,
        )

    def detect_faces(self, frame: np.ndarray) -> list[Box]:
        """Find eye-centered face regions when the per-student mesh is unavailable."""
        frame_height, frame_width = frame.shape[:2]
        detector_frame = frame
        longest = max(frame_width, frame_height)
        if longest > 960:
            scale = 960.0 / longest
            detector_frame = cv2.resize(
                frame,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_AREA,
            )
        rgb = cv2.cvtColor(detector_frame, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb)
        faces: list[Box] = []
        for detection in result.detections or []:
            keypoints = detection.location_data.relative_keypoints
            if len(keypoints) < 2:
                continue
            right_eye, left_eye = keypoints[0], keypoints[1]
            face = self._eye_centered_box(
                right_eye.x,
                right_eye.y,
                left_eye.x,
                left_eye.y,
                0,
                0,
                frame_width,
                frame_height,
                frame_width,
                frame_height,
            )
            if face.area > 0:
                faces.append(face)
        return faces

    def close(self) -> None:
        self._mesh.close()
        self._detector.close()

    @staticmethod
    def _resize_for_face_mesh(crop: np.ndarray) -> np.ndarray:
        height, width = crop.shape[:2]
        longest = max(height, width)
        if 260 <= longest <= 520:
            return crop
        target = 420 if longest < 260 else 520
        scale = target / longest
        return cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)

    @staticmethod
    def _estimate_angles(landmarks) -> tuple[float, float, float]:
        right_eye = landmarks[33]
        left_eye = landmarks[263]
        nose = landmarks[1]
        chin = landmarks[152]

        eye_span = max(0.01, abs(left_eye.x - right_eye.x))
        eye_mid_x = (right_eye.x + left_eye.x) / 2.0
        eye_mid_y = (right_eye.y + left_eye.y) / 2.0
        yaw = (nose.x - eye_mid_x) / eye_span * 120.0

        face_height = max(0.01, chin.y - eye_mid_y)
        pitch = (nose.y - eye_mid_y) / face_height * 90.0
        roll = math.degrees(
            math.atan2(left_eye.y - right_eye.y, left_eye.x - right_eye.x)
        )
        return (
            max(-60.0, min(60.0, float(yaw))),
            max(-60.0, min(60.0, float(pitch))),
            max(-60.0, min(60.0, float(roll))),
        )

    def _estimate_gaze(self, landmarks) -> tuple[float | None, float | None]:
        if len(landmarks) <= self.LEFT_IRIS_CENTER:
            return None, None

        horizontal_ratios = []
        vertical_ratios = []
        for iris_index, corner_indices, lid_indices in (
            (self.RIGHT_IRIS_CENTER, self.RIGHT_EYE_CORNERS, self.RIGHT_EYE_LIDS),
            (self.LEFT_IRIS_CENTER, self.LEFT_EYE_CORNERS, self.LEFT_EYE_LIDS),
        ):
            iris = landmarks[iris_index]
            corner_xs = [landmarks[index].x for index in corner_indices]
            left_x, right_x = min(corner_xs), max(corner_xs)
            eye_width = right_x - left_x
            if eye_width < 0.01:
                continue
            horizontal_ratios.append(
                max(0.0, min(1.0, (iris.x - left_x) / eye_width))
            )

            lid_ys = [landmarks[index].y for index in lid_indices]
            top_y, bottom_y = min(lid_ys), max(lid_ys)
            eye_height = bottom_y - top_y
            if eye_height >= 0.004:
                vertical_ratios.append(
                    max(0.0, min(1.0, (iris.y - top_y) / eye_height))
                )

        horizontal = None
        vertical = None
        if horizontal_ratios:
            horizontal = max(
                -1.0,
                min(1.0, (float(np.mean(horizontal_ratios)) - 0.5) * 2.0),
            )
        if vertical_ratios:
            vertical = max(
                -1.0,
                min(1.0, (float(np.mean(vertical_ratios)) - 0.5) * 2.0),
            )
        return horizontal, vertical

    @staticmethod
    def _face_box(
        landmarks,
        crop_x: int,
        crop_y: int,
        crop_width: int,
        crop_height: int,
        frame_width: int,
        frame_height: int,
    ) -> Box:
        right_eye = landmarks[33]
        left_eye = landmarks[263]
        return HeadPoseEstimator._eye_centered_box(
            right_eye.x,
            right_eye.y,
            left_eye.x,
            left_eye.y,
            crop_x,
            crop_y,
            crop_width,
            crop_height,
            frame_width,
            frame_height,
        )

    @staticmethod
    def _eye_centered_box(
        right_eye_x: float,
        right_eye_y: float,
        left_eye_x: float,
        left_eye_y: float,
        crop_x: int,
        crop_y: int,
        crop_width: int,
        crop_height: int,
        frame_width: int,
        frame_height: int,
    ) -> Box:
        right_x = crop_x + right_eye_x * crop_width
        right_y = crop_y + right_eye_y * crop_height
        left_x = crop_x + left_eye_x * crop_width
        left_y = crop_y + left_eye_y * crop_height
        eye_span = max(12.0, math.hypot(left_x - right_x, left_y - right_y))
        eye_mid_x = (right_x + left_x) / 2.0
        eye_mid_y = (right_y + left_y) / 2.0

        return Box(
            max(0, int(eye_mid_x - eye_span * 0.90)),
            max(0, int(eye_mid_y - eye_span * 0.42)),
            min(frame_width - 1, int(eye_mid_x + eye_span * 0.90)),
            min(frame_height - 1, int(eye_mid_y + eye_span * 1.18)),
        )
