import unittest

from exam_guard.behavior import BehaviorAnalyzer
from exam_guard.config import MonitorConfig
from exam_guard.domain import Box, HeadPose, StudentObservation


class BehaviorAnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.config = MonitorConfig(
            head_yaw_threshold=10.0,
            head_alert_yaw_threshold=18.0,
            risk_warning_score=1.0,
            risk_alert_score=2.0,
            risk_decay_per_second=1.0,
            pose_gap_grace_seconds=0.5,
            incident_cooldown=10.0,
            head_movement_degrees=12.0,
            head_movement_window=4.0,
            head_movement_events=3,
            head_calibration_seconds=0.0,
            gaze_threshold=0.30,
        )
        self.analyzer = BehaviorAnalyzer(self.config)
        self.box = Box(10, 10, 200, 300)

    def observation(
        self, yaw=0.0, track_id=1, gaze=0.0, vertical_gaze=0.0
    ):
        return StudentObservation(
            track_id=track_id,
            box=self.box,
            confidence=0.9,
            head_pose=HeadPose(
                yaw=yaw,
                pitch=0.0,
                roll=0.0,
                gaze_horizontal=gaze,
                gaze_vertical=vertical_gaze,
            ),
        )

    def test_dynamic_strong_head_turn_triggers_an_incident(self):
        first, triggers = self.analyzer.update(self.observation(yaw=0.0), 0.0)
        self.assertEqual(first.status, "Normal")
        self.assertEqual(triggers, [])

        self.analyzer.update(self.observation(yaw=24.0), 0.2)
        self.analyzer.update(self.observation(yaw=24.0), 0.4)
        self.analyzer.update(self.observation(yaw=24.0), 0.8)
        warning, _ = self.analyzer.update(self.observation(yaw=24.0), 1.2)
        self.assertEqual(warning.status, "Warning")

        self.analyzer.update(self.observation(yaw=24.0), 1.6)
        flagged, triggers = self.analyzer.update(self.observation(yaw=24.0), 2.0)
        self.assertEqual(flagged.status, "Suspicious")
        self.assertEqual(triggers[0].behavior, "sustained_head_turn")

        _, duplicate = self.analyzer.update(self.observation(yaw=24.0), 2.4)
        self.assertEqual(duplicate, [])

    def test_forward_pose_decays_dynamic_risk(self):
        self.analyzer.update(self.observation(yaw=0.0), 0.0)
        self.analyzer.update(self.observation(yaw=-25.0), 0.2)
        self.analyzer.update(self.observation(yaw=-25.0), 0.4)
        self.analyzer.update(self.observation(yaw=-25.0), 0.8)
        self.analyzer.update(self.observation(yaw=0.0), 1.0)
        self.analyzer.update(self.observation(yaw=0.0), 1.5)
        self.analyzer.update(self.observation(yaw=0.0), 2.0)
        self.analyzer.update(self.observation(yaw=0.0), 2.5)
        result, triggers = self.analyzer.update(self.observation(yaw=0.0), 3.0)
        self.assertEqual(result.status, "Normal")
        self.assertEqual(result.look_seconds, 0.0)
        self.assertLess(result.risk_score, 1.0)
        self.assertEqual(triggers, [])

    def test_brief_moderate_turn_does_not_create_an_incident(self):
        self.analyzer.update(self.observation(yaw=0.0), 0.0)
        self.analyzer.update(self.observation(yaw=12.0), 0.2)
        self.analyzer.update(self.observation(yaw=12.0), 0.4)
        self.analyzer.update(self.observation(yaw=12.0), 0.8)
        self.analyzer.update(self.observation(yaw=0.0), 1.2)
        result, triggers = self.analyzer.update(self.observation(yaw=0.0), 2.0)

        self.assertEqual(result.status, "Normal")
        self.assertEqual(triggers, [])

    def test_dynamic_side_gaze_triggers_an_incident(self):
        self.analyzer.update(self.observation(gaze=0.0), 7.0)
        self.analyzer.update(self.observation(gaze=-0.7), 7.2)
        self.analyzer.update(self.observation(gaze=-0.7), 7.4)
        self.analyzer.update(self.observation(gaze=-0.7), 7.8)
        warning, triggers = self.analyzer.update(self.observation(gaze=-0.7), 8.2)
        self.assertEqual(warning.status, "Warning")
        self.assertEqual(triggers, [])

        self.analyzer.update(self.observation(gaze=-0.7), 8.6)
        flagged, triggers = self.analyzer.update(self.observation(gaze=-0.7), 9.0)
        self.assertEqual(flagged.status, "Suspicious")
        self.assertEqual(triggers[0].behavior, "side_gaze")

        held, duplicate = self.analyzer.update(self.observation(gaze=0.0), 9.2)
        self.assertEqual(held.status, "Suspicious")
        self.assertEqual(duplicate, [])

    def test_downward_writing_gaze_does_not_trigger_side_gaze(self):
        self.analyzer.update(self.observation(gaze=0.0), 20.0)
        result = None
        triggers = []
        for timestamp in (20.2, 20.5, 21.0, 21.5):
            result, new_triggers = self.analyzer.update(
                self.observation(gaze=-0.8, vertical_gaze=0.9), timestamp
            )
            triggers.extend(new_triggers)

        self.assertEqual(result.status, "Normal")
        self.assertEqual(triggers, [])

    def test_repeated_head_movements_trigger_an_incident(self):
        self.config.risk_warning_score = 5.0
        self.config.risk_alert_score = 10.0
        analyzer = BehaviorAnalyzer(self.config)
        analyzer.update(self.observation(yaw=0.0), 10.0)
        analyzer.update(self.observation(yaw=20.0), 10.4)
        analyzer.update(self.observation(yaw=20.0), 10.8)
        analyzer.update(self.observation(yaw=-20.0), 11.2)
        analyzer.update(self.observation(yaw=-20.0), 11.6)
        analyzer.update(self.observation(yaw=20.0), 12.0)
        flagged, triggers = analyzer.update(self.observation(yaw=20.0), 12.4)

        self.assertEqual(flagged.status, "Suspicious")
        self.assertEqual(flagged.movement_count, 3)
        self.assertIn("repeated_head_movement", [trigger.behavior for trigger in triggers])

    def test_calibration_normalizes_each_students_camera_angle(self):
        config = MonitorConfig(
            head_calibration_seconds=1.0,
            head_yaw_threshold=10.0,
        )
        analyzer = BehaviorAnalyzer(config)
        first, _ = analyzer.update(self.observation(yaw=35.0, track_id=9), 0.0)
        analyzer.update(self.observation(yaw=35.0, track_id=9), 0.5)
        calibrated, _ = analyzer.update(self.observation(yaw=35.0, track_id=9), 1.0)
        stable, triggers = analyzer.update(self.observation(yaw=35.0, track_id=9), 3.0)

        self.assertEqual(first.direction, "Calibrating")
        self.assertEqual(calibrated.direction, "Forward")
        self.assertEqual(stable.status, "Normal")
        self.assertEqual(stable.look_seconds, 0.0)
        self.assertEqual(triggers, [])


if __name__ == "__main__":
    unittest.main()
