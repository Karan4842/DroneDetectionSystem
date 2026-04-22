# Drone Threat Command Dashboard

An AI-based drone threat monitoring system for restricted or sensitive areas such as airport perimeters. The project combines computer vision, threat analysis, geofencing, alert logging, a FastAPI backend, and a React dashboard to support real-time monitoring and easy image-based testing.

## Overview

This project is designed to detect and monitor possible drone threats in protected airspace. It supports:

- Live webcam monitoring
- Image upload testing directly from the dashboard
- Threat scoring based on detection confidence, movement, and restricted-zone intrusion
- Alert logging with saved evidence images
- A React frontend for operator-style monitoring
- A FastAPI backend for runtime status, alerts, and image analysis

At a high level, the system flow is:

```text
Camera / Image
    -> YOLO Detection
    -> Object Tracking
    -> Geofencing Check
    -> Threat Scoring
    -> Alert Logging
    -> FastAPI
    -> React Dashboard
```

## Features

- Real-time object detection using YOLO
- Basic object tracking using a centroid tracker
- Restricted zone monitoring using configurable geofencing areas
- Threat severity scoring
- Evidence snapshot generation for alert events
- Alert history and incident review
- Live runtime status on the dashboard
- Image upload from the dashboard without opening the detector manually
- Dashboard controls to start and stop the camera detector

## Tech Stack

### AI / Computer Vision
- Python
- Ultralytics YOLO
- OpenCV
- NumPy

### Backend
- FastAPI
- Uvicorn

### Frontend
- React
- Vite
- CSS

### Data / Storage
- JSON / JSONL logs
- Local image evidence storage

## Project Structure

```text
DroneDetectionSystem/
├── api.py
├── main.py
├── security.py
├── tracker.py
├── reporting.py
├── security_config.json
├── requirements.txt
├── README.md
├── start_api.bat
├── start_frontend.bat
├── start_live_detector.bat
├── start_dashboard_only.bat
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       └── styles.css
├── outputs/
│   ├── alerts/
│   ├── logs/
│   └── uploads/
└── sample_inputs/
```

## Important Modules

- `main.py`
  Runs the detection pipeline on webcam, image, or video input.

- `security.py`
  Handles geofencing, threat scoring, overlays, logging helpers, and runtime status writing.

- `tracker.py`
  Provides basic object tracking and track IDs.

- `api.py`
  Exposes backend endpoints for alerts, runtime status, detector controls, and uploaded-image analysis.

- `frontend/src/App.jsx`
  React dashboard for monitoring, alert review, and image upload testing.

## Threat Analysis Logic

The system does more than simple object detection. It evaluates risk using:

- detection confidence
- restricted-zone intrusion
- object size in frame
- track duration
- estimated motion speed
- movement toward a protected zone

Based on these factors, each detection is assigned a severity such as:

- low
- medium
- high
- critical

## Configuration

The project is configured through:

- `security_config.json`

This file controls:

- site name
- suspicious classes
- restricted zones
- risk weights
- confidence thresholds
- tracking thresholds
- alert thresholds

## How to Run

### Easiest Option

From:

```text
F:\DroneDetectionSystem\DroneDetectionSystem
```

run:

```bat
start_dashboard_only.bat
```

Then open:

```text
http://localhost:5173
```

This starts:

- FastAPI backend
- React frontend

From the dashboard, you can:

- click `Open Camera` to start live monitoring
- click `Stop Camera` to stop it
- upload an image in `Quick Image Test`

### Manual Run

Backend:

```bat
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Frontend:

```bat
cd frontend
cmd /c npm run dev
```

Detector directly:

```bat
python main.py --source 0 --show-labels
```

## Image Testing

You can test using the dashboard upload, or manually place files in:

```text
sample_inputs/
```

Manual example:

```bat
python main.py --source sample_inputs\drone1.jpg --show-labels
```

## Outputs

Generated files are stored under:

- `outputs/logs/alerts.jsonl`
- `outputs/logs/runtime_status.json`
- `outputs/alerts/`
- `outputs/uploads/results/`

These contain:

- alert history
- live detector status
- evidence snapshots
- annotated uploaded-image results

## Current Limitations

- The default `yolov8n.pt` model is a general-purpose model, not a custom drone-trained model.
- Tracking uses a centroid tracker instead of DeepSORT.
- Threat scoring is rule-based rather than a trained threat-classification model.
- Live video is shown in a detector window, not yet embedded directly into the React dashboard.

## Future Improvements

- Use a custom-trained drone detection model
- Add DeepSORT-based tracking
- Add live video streaming inside the dashboard
- Add database-backed incident storage
- Add SMS/email alerts
- Add multi-camera monitoring
- Add trajectory prediction

## Resume Description

Built an AI-based drone threat monitoring system for restricted airspace using YOLO, OpenCV, FastAPI, and React. Implemented object detection, tracking, geofencing, threat scoring, alert logging, evidence capture, and a web dashboard for live monitoring and image-based testing.

## Notes

For the best results in real drone detection, replace the generic YOLO model with a custom drone-trained `.pt` model.
