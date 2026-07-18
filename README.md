# Exam Sentinel

Exam Sentinel is a Python desktop application for reviewing suspicious behavior in exam video. It detects and tracks students, checks sustained head turns, side gaze, lateral body shifts, and repeated left/right head turns, draws green/amber/red student boxes, saves incident screenshots, records events in SQLite, and shows desktop alerts.

The application flags evidence for a human reviewer. It does not decide that a student cheated.

## Included features

- YOLO11 person detection using pretrained COCO weights
- BoT-SORT multi-student tracking with duplicate suppression and seat-stable IDs
- MediaPipe face landmarks with a per-student neutral head-angle calibration
- Face/iris landmarks plus full-frame face fallback for eye-centered boxes and gaze
- Per-student seat calibration for sustained lateral body-movement evidence
- Repeated alternating left/right head-movement detection per tracked student
- Adaptive per-student head/eye risk scoring with configurable thresholds and decay
- Green normal, amber warning, and red suspicious bounding boxes
- Automatic JPEG evidence in `screenshots/`
- SQLite incident history in `data/incidents.db`
- Review, false-alarm, and open-evidence actions
- Remove one incident or clear all visible history while keeping saved evidence files
- Direct Camera 0 input, video-file input, pause, and stop controls
- Purpose-built dark review interface with live student focus and incident queues
- Automatic CUDA use through the RTX 4070 environment

No training dataset is required for this first version. Test it with your own classroom or exam videos, then collect and label local examples only if the pretrained detector is not reliable for your camera angle.

## One-time setup

Open the folder in VS Code:

```powershell
cd "D:\CV_INSTANT\Project 3"
code .
```

In the VS Code terminal, run:

```powershell
.\setup.ps1
```

The setup creates `.venv`, reuses the CUDA-enabled `subway_rl` environment, installs PyQt6 and MediaPipe, and downloads `models/yolo11n.pt`.

## Run

```powershell
.\run.ps1
```

You can also press `F5` and choose `Exam Sentinel`, or start Camera 0 directly:

```powershell
.\run.ps1 --camera 0
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Default adaptive rules

| Signal | Default rule |
|---|---|
| Initial calibration | Learn each student's neutral head angle for 2 seconds |
| Head direction | A left/right turn beyond 18 degrees held for 1 second creates an incident |
| Side gaze | Relative iris shift beyond 0.35 held for 1 second creates an incident; strong downward writing gaze is ignored |
| Body movement | A lateral shift beyond 0.15 body widths held for 1 second creates an incident |
| Head + eyes | Matching head and eye direction receives a 1.35x evidence multiplier |
| Recovery | Risk decreases by 1.25 points per second while behavior is normal |
| Thresholds | Amber at risk 2.0; red and incident evidence at risk 5.0 |
| Landmark gap | Preserve recent evidence for 0.6 seconds instead of resetting immediately |
| Repeated head movement | 3 alternating left/right turns of at least 20 degrees within 4 seconds reaches alert risk |
| Repeat incident | Same signal can alert again after 15 seconds |

Tune these values from **Settings** before starting a source. Camera placement matters: faces should be visible, and students should be large enough in the frame for face landmarks to resolve.

## Saved history

Adaptive scoring uses the source video's timestamps, so risk does not change when
processing FPS is slower than playback FPS. One continuous behavior
episode creates at most one incident screenshot, and a confirmed student's box stays
red for five seconds so a brief landmark dropout does not hide the alert.

Incident details persist in `data/incidents.db`. Evidence screenshots persist in
`screenshots/`. Use **Delete selected** to remove one database record, or **Clear
history** to remove all database records. Both actions keep the screenshot files;
use **Evidence folder** to open them. **Select all** selects every visible incident;
multi-row selections also work with review, false-alarm, and delete actions.

## Project structure

```text
main.py                 Application entry point
exam_guard/ui.py        PyQt6 desktop interface
exam_guard/worker.py    Background video loop
exam_guard/vision.py    YOLO detection, tracking, association, drawing
exam_guard/head_pose.py MediaPipe landmark head pose
exam_guard/behavior.py  Adaptive head/eye risk scoring and alert rules
exam_guard/database.py  SQLite incidents and screenshot recording
tests/                  Behavior and database tests
```
