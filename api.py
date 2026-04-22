from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

os.environ.setdefault("YOLO_CONFIG_DIR", "outputs")

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

from reporting import build_alert_analytics, build_text_report, load_alerts
from security import (
    enrich_detections,
    extract_detections,
    load_config,
    normalize_classes,
    resolve_model_source,
)
from tracker import CentroidTracker


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LOG_PATH = OUTPUTS_DIR / "logs" / "alerts.jsonl"
CONFIG_PATH = BASE_DIR / "security_config.json"
ALERTS_DIR = OUTPUTS_DIR / "alerts"
RUNTIME_STATUS_PATH = OUTPUTS_DIR / "logs" / "runtime_status.json"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
UPLOAD_RESULTS_DIR = UPLOADS_DIR / "results"
LIVE_DIR = OUTPUTS_DIR / "live"
SAMPLE_INPUTS_DIR = BASE_DIR / "sample_inputs"
MODEL_PATH = BASE_DIR.parent / "yolov8n.pt"

ALERTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LIVE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Drone Threat API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/evidence", StaticFiles(directory=str(ALERTS_DIR)), name="evidence")
app.mount("/artifacts", StaticFiles(directory=str(UPLOAD_RESULTS_DIR)), name="artifacts")
app.mount("/live", StaticFiles(directory=str(LIVE_DIR)), name="live")

_model: YOLO | None = None
_detector_process: subprocess.Popen | None = None


def build_summary(alerts: list[dict]) -> dict:
    severity_counter = Counter()
    zone_counter = Counter()
    active_tracks = set()

    for event in alerts:
        for alert in event.get("alerts", []):
            severity_counter[alert.get("severity", "unknown")] += 1
            track_id = alert.get("track_id")
            if track_id is not None:
                active_tracks.add(track_id)
            for zone_name in alert.get("violated_zones", []):
                zone_counter[zone_name] += 1

    recent_event = alerts[-1] if alerts else None
    return {
        "total_events": len(alerts),
        "tracked_threats": len(active_tracks),
        "critical_alerts": severity_counter.get("critical", 0),
        "high_alerts": severity_counter.get("high", 0),
        "severity_breakdown": dict(severity_counter),
        "zone_breakdown": dict(zone_counter),
        "latest_event": recent_event,
    }


def serialize_event(event: dict) -> dict:
    evidence_frame = event.get("evidence_frame")
    evidence_name = Path(evidence_frame).name if evidence_frame else None
    return {
        **event,
        "evidence_url": f"/evidence/{evidence_name}" if evidence_name else None,
    }


def read_runtime_status() -> dict:
    if not RUNTIME_STATUS_PATH.exists():
        return {
            "running": False,
            "site_name": load_config(str(CONFIG_PATH)).get("site_name"),
            "source": None,
            "resolved_source": None,
            "frame_index": 0,
            "active_tracks": 0,
            "active_alerts": 0,
            "last_updated_epoch": None,
            "last_updated_utc": None,
            "latest_detections": [],
            "image_mode": False,
        }
    return json.loads(RUNTIME_STATUS_PATH.read_text(encoding="utf-8"))


def detector_process_running() -> bool:
    return _detector_process is not None and _detector_process.poll() is None


def detector_control_status() -> dict:
    runtime = read_runtime_status()
    return {
        "running": runtime.get("running", False),
        "runtime": runtime,
        "managed_by_api": detector_process_running(),
        "pid": _detector_process.pid if detector_process_running() else None,
    }


def get_model() -> YOLO:
    global _model
    if _model is None:
        model_source = str(MODEL_PATH) if MODEL_PATH.exists() else "yolov8n.pt"
        _model = YOLO(resolve_model_source(model_source))
    return _model


def analyze_image_file(image_path: Path) -> dict:
    config = load_config(str(CONFIG_PATH))
    model = get_model()
    tracker = CentroidTracker(
        max_distance=float(config["tracking_thresholds"]["max_distance_pixels"]),
        max_missed_frames=int(config["tracking_thresholds"]["max_missed_frames"]),
    )
    watched_classes = normalize_classes(config.get("suspicious_classes", []))

    results = model.predict(
        source=str(image_path),
        stream=False,
        conf=float(config["confidence_thresholds"]["detection"]),
        verbose=False,
    )
    result = results[0]
    frame = result.orig_img.copy()
    raw_detections = extract_detections(result, watched_classes)
    tracker.update(raw_detections, 0)
    detections = enrich_detections(
        frame=frame,
        detections=raw_detections,
        tracker_tracks=tracker.tracks,
        show_labels=bool(config.get("show_labels", True)),
        config=config,
    )

    UPLOAD_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    output_name = f"analysis_{uuid4().hex}.jpg"
    output_path = UPLOAD_RESULTS_DIR / output_name
    cv2.imwrite(str(output_path), frame)

    return {
        "site_name": config["site_name"],
        "detections": detections,
        "threat_count": len(detections),
        "high_risk_count": sum(1 for item in detections if item["risk_score"] >= config["alert_threshold"]),
        "annotated_image_url": f"/artifacts/{output_name}",
    }


def list_sample_inputs() -> list[str]:
    if not SAMPLE_INPUTS_DIR.exists():
        return []

    return sorted(
        file.name
        for file in SAMPLE_INPUTS_DIR.iterdir()
        if file.is_file() and file.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config")
def config() -> dict:
    return load_config(str(CONFIG_PATH))


@app.get("/summary")
def summary() -> dict:
    alerts = load_alerts(LOG_PATH)
    return {
        **build_summary(alerts),
        "runtime": read_runtime_status(),
    }


@app.get("/analytics")
def analytics() -> dict:
    alerts = load_alerts(LOG_PATH)
    return {
        **build_alert_analytics(alerts),
        "runtime": read_runtime_status(),
    }


@app.get("/runtime")
def runtime() -> dict:
    return read_runtime_status()


@app.get("/detector/status")
def detector_status() -> dict:
    return detector_control_status()


@app.get("/alerts")
def alerts(limit: int = 20) -> list[dict]:
    items = load_alerts(LOG_PATH)
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be greater than zero")
    return [serialize_event(event) for event in items[-limit:]][::-1]


@app.get("/alerts/{event_id}")
def alert_by_id(event_id: str) -> dict:
    items = load_alerts(LOG_PATH)
    for event in reversed(items):
        if event.get("event_id") == event_id:
            return serialize_event(event)
    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/report", response_class=PlainTextResponse)
def report() -> str:
    alerts = load_alerts(LOG_PATH)
    return build_text_report(alerts)


@app.get("/demo/scenarios")
def demo_scenarios() -> dict:
    samples = list_sample_inputs()
    return {
        "samples": samples,
        "default_sample": samples[0] if samples else None,
    }


@app.post("/demo/run")
def demo_run(sample: str | None = None) -> dict:
    samples = list_sample_inputs()
    if not samples:
        raise HTTPException(status_code=404, detail="No demo samples are available.")

    chosen_sample = sample if sample in samples else samples[0]
    sample_path = SAMPLE_INPUTS_DIR / chosen_sample
    result = analyze_image_file(sample_path)

    result.update(
        {
            "demo_mode": True,
            "sample_name": chosen_sample,
            "message": f"Demo scenario loaded from {chosen_sample}.",
        }
    )
    return result


@app.post("/analyze-image")
async def analyze_image(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "upload.jpg").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
        raise HTTPException(status_code=400, detail="Upload a valid image file.")

    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = UPLOADS_DIR / f"upload_{uuid4().hex}{suffix}"
    upload_path.write_bytes(await file.read())
    return analyze_image_file(upload_path)


@app.post("/detector/start")
def start_detector() -> dict:
    global _detector_process

    if detector_process_running():
        return {
            "message": "Detector is already running.",
            **detector_control_status(),
        }

    model_source = str(MODEL_PATH) if MODEL_PATH.exists() else "yolov8n.pt"
    command = [
        sys.executable,
        "main.py",
        "--source",
        "0",
        "--model",
        model_source,
        "--show-labels",
    ]
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    log_path = OUTPUTS_DIR / "logs" / "detector_stdout.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("a", encoding="utf-8")
    _detector_process = subprocess.Popen(
        command,
        cwd=str(BASE_DIR),
        stdout=log_file,
        stderr=log_file,
        creationflags=creationflags,
    )
    return {
        "message": "Detector started.",
        **detector_control_status(),
    }


@app.post("/detector/stop")
def stop_detector() -> dict:
    global _detector_process

    if not detector_process_running():
        _detector_process = None
        return {
            "message": "Detector is not running.",
            **detector_control_status(),
        }

    _detector_process.terminate()
    try:
        _detector_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _detector_process.kill()
        _detector_process.wait(timeout=5)

    _detector_process = None
    return {
        "message": "Detector stopped.",
        **detector_control_status(),
    }
