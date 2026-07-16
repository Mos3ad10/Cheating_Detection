import tempfile
import unittest
from pathlib import Path

from exam_guard.database import IncidentDatabase


class IncidentDatabaseTests(unittest.TestCase):
    def test_incident_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            database = IncidentDatabase(Path(directory) / "incidents.db")
            incident = database.add_incident(
                occurred_at="2026-07-15T10:30:00+03:00",
                track_id=7,
                behavior="Looking left for 4.2s",
                confidence=0.82,
                screenshot_path=str(Path(directory) / "evidence.jpg"),
                source="exam.mp4",
            )
            evidence_path = Path(incident["screenshot_path"])
            evidence_path.write_bytes(b"saved evidence")
            self.assertEqual(incident["status"], "Needs review")
            self.assertEqual(database.list_incidents()[0]["track_id"], 7)

            database.update_status(incident["id"], "Reviewed")
            self.assertEqual(database.list_incidents()[0]["status"], "Reviewed")

            deleted_path = database.delete_incident(incident["id"])
            self.assertEqual(deleted_path, incident["screenshot_path"])
            self.assertEqual(database.list_incidents(), [])
            self.assertTrue(evidence_path.exists())

            first = database.add_incident(
                "2026-07-15T10:31:00+03:00", 8, "Head movement", 0.9,
                str(Path(directory) / "first.jpg"), "exam.mp4"
            )
            second = database.add_incident(
                "2026-07-15T10:32:00+03:00", 9, "Head movement", 0.8,
                str(Path(directory) / "second.jpg"), "exam.mp4"
            )
            first_evidence = Path(first["screenshot_path"])
            second_evidence = Path(second["screenshot_path"])
            first_evidence.write_bytes(b"first evidence")
            second_evidence.write_bytes(b"second evidence")
            cleared_paths = database.clear_incidents()
            self.assertEqual(
                set(cleared_paths),
                {first["screenshot_path"], second["screenshot_path"]},
            )
            self.assertEqual(database.list_incidents(), [])
            self.assertTrue(first_evidence.exists())
            self.assertTrue(second_evidence.exists())
            database.close()


if __name__ == "__main__":
    unittest.main()
