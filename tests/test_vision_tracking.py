import unittest

from exam_guard.domain import Box, HeadPose, TrackedStudent
from exam_guard.vision import ExamVisionPipeline, _StableIdentityTracker


class VisionTrackingTests(unittest.TestCase):
    def test_nested_duplicate_person_boxes_are_removed(self):
        people = [
            (Box(100, 100, 300, 500), 0.92, 4),
            (Box(112, 112, 292, 492), 0.70, 9),
            (Box(330, 100, 520, 500), 0.88, 5),
        ]

        kept = ExamVisionPipeline._deduplicate_people(people)

        self.assertEqual(len(kept), 2)
        self.assertEqual({raw_id for _, _, raw_id in kept}, {4, 5})

    def test_raw_id_change_at_same_seat_keeps_stable_id(self):
        tracker = _StableIdentityTracker()
        first = tracker.assign(Box(500, 100, 650, 420), 0.0, set(), 5)
        changed = tracker.assign(Box(508, 105, 656, 425), 2.0, set(), 7)
        changed_again = tracker.assign(Box(516, 108, 664, 428), 5.0, set(), 10)

        self.assertEqual(first, 5)
        self.assertEqual(changed, first)
        self.assertEqual(changed_again, first)

    def test_nearby_students_keep_different_ids(self):
        tracker = _StableIdentityTracker()
        first = tracker.assign(Box(100, 100, 260, 500), 0.0, set(), 1)
        second = tracker.assign(Box(330, 100, 490, 500), 0.0, {first}, 2)

        self.assertEqual(first, 1)
        self.assertEqual(second, 2)

    def test_face_hint_prevents_two_students_using_the_same_face(self):
        overlapping_body = TrackedStudent(3, Box(600, 500, 2000, 2100), 0.9)
        correct_body = TrackedStudent(6, Box(450, 600, 1250, 2100), 0.8)
        same_face = Box(900, 650, 1200, 1050)
        pose = HeadPose(0.0, 0.0, 0.0, same_face)

        accepted, rejected = ExamVisionPipeline._select_unique_face_poses(
            [(overlapping_body, pose), (correct_body, pose)],
            {6: same_face},
        )

        self.assertEqual([student.track_id for student, _ in accepted], [6])
        self.assertEqual(rejected, {3})


if __name__ == "__main__":
    unittest.main()
