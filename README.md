# Exam Sentinel

Exam Sentinel is a dark-themed Python desktop application for AI-assisted exam
monitoring and incident review. It detects and tracks multiple students, evaluates
head direction, side eye gaze, lateral body shifts, and repeated head movement,
then saves reviewable evidence when configured rules are reached.

> Exam Sentinel highlights behavior for a human reviewer. It does not determine
> that a student cheated.

## Highlights

- Multi-student person detection with YOLO11
- BoT-SORT tracking with duplicate suppression and seat-stable student IDs
- MediaPipe face and iris landmarks for calibrated head pose and eye gaze
- Per-student seat calibration for lateral body-shift detection
- One-second sustained alerts for head turns, side gaze, and body shifts
- Repeated alternating left/right head-movement detection
- Green, amber, and red overlays for normal, warning, and suspicious states
- Automatic incident screenshots and persistent SQLite history
- Review, false-alarm, evidence, multi-select, delete, and clear-history actions
- Professional PyQt6 desktop interface with live analysis and review queues
- Direct Camera 0 startup with no camera-selection menu
- Video-file analysis with pause and stop controls
- Automatic CUDA use when supported by the active PyTorch environment

## Detection Pipeline

```text
Camera 0 or exam video
        |
        v
YOLO11 person detection
        |
        v
BoT-SORT tracking and stable student IDs
        |
        v
MediaPipe head pose and iris gaze + body-position baseline
        |
        v
Per-student behavior scoring and one-second sustained rules
        |
        +--> Live colored overlays and student focus table
        |
        +--> Evidence screenshot and SQLite incident queue
```

Behavior timing for video files uses the video's own timestamps. Detection speed
therefore does not change the meaning of a one-second rule.

## Default Rules

| Signal | Default behavior |
|---|---|
| Initial calibration | Learn each student's neutral head angle and seat position for 2 seconds |
| Sustained head turn | Left/right turn beyond 18 degrees for 1 second |
| Sustained side gaze | Relative iris shift beyond 0.35 for 1 second |
| Writing-gaze filter | Ignore side-gaze evidence when vertical gaze exceeds 0.65 |
| Sustained body shift | Lateral movement beyond 0.15 body widths for 1 second |
| Head and eyes | Matching directions receive a 1.35x evidence multiplier |
| Repeated head movement | 3 alternating turns of at least 20 degrees within 4 seconds |
| Warning threshold | Risk score 2.0 |
| Incident threshold | Risk score 5.0 |
| Recovery | Risk decreases by 1.25 points per second during normal behavior |
| Landmark grace | Preserve recent evidence for 0.6 seconds during brief landmark loss |
| Repeat incident | Allow the same signal to create another incident after 15 seconds |

All detection values can be changed from **Detection settings** before monitoring
starts.

## Desktop Workflow

1. Select **Start live camera** to open Camera 0, or select **Open exam video**.
2. Wait for each visible student to complete the short calibration period.
3. Monitor the live analysis stage and the **Student focus** table.
4. Review new evidence in the **Incident queue**.
5. Mark each selected incident as reviewed or as a false alarm.

The pause, stop, evidence-folder, select-all, delete-selected, and clear-history
controls remain available throughout the review workflow. Deleting database records
does not delete their saved evidence screenshots.

## Requirements

- Windows 10 or Windows 11
- Python 3.10.19
- A webcam for live monitoring, or a supported exam video
- Optional NVIDIA CUDA environment for GPU acceleration

Core packages are pinned in `requirements.txt`:

- PyQt6
- MediaPipe
- OpenCV
- PyTorch
- Ultralytics YOLO
- NumPy
- LAP

## Installation

Clone the repository and enter the project folder:

```powershell
git clone https://github.com/Mos3ad10/Cheating_Detection.git
cd Cheating_Detection
```

Run the setup script with the Python installation or Conda environment that should
provide the base runtime:

```powershell
.\setup.ps1 -BasePython "C:\path\to\python.exe"
```

The setup script creates `.venv`, installs the pinned dependencies, downloads the
pretrained `yolo11n.pt` model into `models/`, and reports the selected PyTorch
device. On the original development machine, running `.\setup.ps1` without an
argument uses the configured `subway_rl` Conda environment.

## Run

Open the desktop application:

```powershell
.\run.ps1
```

Optional command-line sources:

```powershell
.\run.ps1 --camera 0
.\run.ps1 --video "D:\path\to\exam-video.mp4"
```

The desktop camera button always uses Camera 0. Other camera indexes remain
available through the `--camera` command-line option.

## Evidence and History

Generated runtime data is kept locally:

```text
data/incidents.db   Persistent SQLite incident history
screenshots/        JPEG evidence captured when an incident is created
```

One continuous behavior episode creates at most one incident until the signal
clears. A suspicious student's overlay remains red for five seconds so a brief
landmark dropout does not immediately hide the alert.

## Tests

Run the complete test suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The tests cover sustained head, eye, and body behavior; normal recovery; downward
writing gaze; body-box jitter; repeated movement; stable tracking IDs; duplicate
suppression; unique face assignment; and the SQLite incident lifecycle.

## Project Structure

```text
main.py                  Application entry point and command-line source options
exam_guard/config.py     Detection thresholds and validation
exam_guard/domain.py     Shared observations, results, boxes, and incidents
exam_guard/worker.py     Background capture and analysis thread
exam_guard/vision.py     YOLO tracking, face association, and frame overlays
exam_guard/head_pose.py  MediaPipe head-pose and iris-gaze estimation
exam_guard/behavior.py   Head, eye, body, movement, and risk rules
exam_guard/database.py   SQLite incident history and evidence recording
exam_guard/ui.py         PyQt6 desktop interface and reviewer actions
exam_guard/theme.py      Dark desktop visual system
tests/                   Behavior, tracking, and database tests
```

## Responsible Use

Camera position, lighting, face size, occlusion, seating layout, and detector
quality can all affect results. Validate thresholds with representative local exam
footage before deployment, protect stored evidence, limit access to authorized
reviewers, and require a person to evaluate every flag in context.
