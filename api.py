from __future__ import annotations

import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import AsyncGenerator
from uuid import uuid4

os.environ.setdefault("YOLO_CONFIG_DIR", "outputs")

import cv2
from fastapi import Body, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO

from reporting import (
    build_alert_analytics,
    build_csv_report,
    build_json_export,
    build_text_report,
    load_alerts,
)
from security import (
    enrich_detections,
    extract_detections,
    generate_sensor_telemetry,
    load_config,
    normalize_classes,
    resolve_model_source,
    save_config,
)
from tracker import CentroidTracker


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LOGS_DIR = OUTPUTS_DIR / "logs"
LOG_PATH = LOGS_DIR / "alerts.jsonl"
COUNTERMEASURES_LOG_PATH = LOGS_DIR / "countermeasures.jsonl"
CONFIG_PATH = BASE_DIR / "security_config.json"
ALERTS_DIR = OUTPUTS_DIR / "alerts"
RUNTIME_STATUS_PATH = LOGS_DIR / "runtime_status.json"
UPLOADS_DIR = OUTPUTS_DIR / "uploads"
UPLOAD_RESULTS_DIR = UPLOADS_DIR / "results"
LIVE_DIR = OUTPUTS_DIR / "live"
SAMPLE_INPUTS_DIR = BASE_DIR / "sample_inputs"
MODEL_PATH = BASE_DIR.parent / "yolov8n.pt"

ALERTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
LIVE_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Drone Threat Command & Detection API",
    description="Enterprise Multi-Sensor Drone Detection, Geofencing, and C-UAS Countermeasure API",
    version="2.0.0"
)

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
_active_countermeasures: list[dict] = []


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
            "site_name": load_config(str(CONFIG_PATH)).get("site_name", "Perimeter Zone"),
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
    try:
        return json.loads(RUNTIME_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"running": False, "site_name": "Perimeter Zone", "active_tracks": 0}


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
        max_distance=float(config.get("tracking_thresholds", {}).get("max_distance_pixels", 80)),
        max_missed_frames=int(config.get("tracking_thresholds", {}).get("max_missed_frames", 20)),
    )
    watched_classes = normalize_classes(config.get("suspicious_classes", []))

    results = model.predict(
        source=str(image_path),
        stream=False,
        conf=float(config.get("confidence_thresholds", {}).get("detection", 0.3)),
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
        "high_risk_count": sum(1 for item in detections if item["risk_score"] >= config.get("alert_threshold", 70)),
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


# --- Video Streaming Generator (MJPEG) ---
async def mjpeg_frame_generator() -> AsyncGenerator[bytes, None]:
    """
    Yields live JPEG frames in MJPEG stream format.
    Streams latest.jpg from running detector, or falls back to animated test frames with YOLO inference.
    """
    latest_frame_file = LIVE_DIR / "latest.jpg"
    sample_files = list_sample_inputs()
    sample_idx = 0
    config = load_config(str(CONFIG_PATH))
    model = get_model()
    tracker = CentroidTracker()

    while True:
        frame_bytes = None

        # 1. Prefer live frame generated by active detector (managed process OR external main.py)
        is_live_active = detector_process_running()
        if not is_live_active and latest_frame_file.exists():
            try:
                # If modified within the last 4 seconds, treat as active live feed
                if (time.time() - latest_frame_file.stat().st_mtime) < 4.0:
                    is_live_active = True
            except Exception:
                pass

        if is_live_active and latest_frame_file.exists():
            try:
                frame_bytes = latest_frame_file.read_bytes()
            except Exception:
                pass

        # 2. Fallback: Stream sample simulation frames
        if frame_bytes is None:
            if sample_files:
                sample_path = SAMPLE_INPUTS_DIR / sample_files[sample_idx % len(sample_files)]
                img = cv2.imread(str(sample_path))
                if img is not None:
                    # Run lightweight inference
                    results = model.predict(source=img, conf=0.25, verbose=False)
                    raw_dets = extract_detections(results[0], normalize_classes(config.get("suspicious_classes", [])))
                    tracker.update(raw_dets, sample_idx)
                    enrich_detections(img, raw_dets, tracker.tracks, True, config)
                    
                    # Add simulation badge overlay
                    cv2.putText(
                        img,
                        "SIMULATION FEED (Start Detector for Live Camera)",
                        (15, 30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55,
                        (0, 215, 255),
                        2,
                    )
                    _, buffer = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    frame_bytes = buffer.tobytes()
                    sample_idx += 1
            else:
                # Synthetic radar placeholder frame
                blank = 30 * cv2.UMat(480, 640, cv2.CV_8UC3).get()
                cv2.putText(blank, "Awaiting Camera Feed...", (140, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (116, 216, 208), 2)
                cv2.putText(blank, "Click 'Start Live Detector' to connect camera", (100, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 180, 190), 1)
                _, buffer = cv2.imencode(".jpg", blank)
                frame_bytes = buffer.tobytes()

        if frame_bytes:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

        await asyncio.sleep(0.12)  # ~8-10 FPS for bandwidth-friendly dashboard preview


# --- Endpoints ---

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "2.0.0", "system": "Drone Threat Command"}


@app.get("/config")
def get_configuration() -> dict:
    return load_config(str(CONFIG_PATH))


@app.put("/config")
def update_configuration(new_config: dict = Body(...)) -> dict:
    save_config(new_config, str(CONFIG_PATH))
    return {"status": "success", "message": "Configuration updated successfully", "config": new_config}


@app.post("/config/zones")
def update_zones(zones: list[dict] = Body(...)) -> dict:
    config = load_config(str(CONFIG_PATH))
    config["restricted_zones"] = zones
    save_config(config, str(CONFIG_PATH))
    return {"status": "success", "restricted_zones": zones}


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


@app.get("/video_feed")
def video_feed():
    """Real-time MJPEG video stream with bounding boxes and zone overlays."""
    return StreamingResponse(
        mjpeg_frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/sensors/telemetry")
def sensor_telemetry() -> dict:
    """Multi-sensor telemetry stream (Radar tracks, RF signatures, Acoustic analytics)."""
    runtime = read_runtime_status()
    config = load_config(str(CONFIG_PATH))
    latest_detections = runtime.get("latest_detections", [])
    return generate_sensor_telemetry(
        detections=latest_detections,
        site_name=config.get("site_name", "Protected Area"),
        config=config
    )


@app.get("/countermeasures/status")
def countermeasures_status() -> dict:
    """Returns active and historical C-UAS mitigation actions."""
    if not COUNTERMEASURES_LOG_PATH.exists():
        logs = []
    else:
        logs = [
            json.loads(line)
            for line in COUNTERMEASURES_LOG_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ][-20:]
    return {
        "active_engagements": _active_countermeasures,
        "total_engagements": len(logs),
        "recent_logs": logs[::-1]
    }


@app.post("/countermeasures/trigger")
def trigger_countermeasure(
    action: str = Query(..., description="Action: RF_JAMMING_DIRECTIONAL, GNSS_SPOOFING_DEFENSE, ACOUSTIC_SIREN, ATC_NOTIFY"),
    target_track_id: int | None = Query(None, description="Optional target track ID")
) -> dict:
    """Dispatches a C-UAS countermeasure action."""
    valid_actions = {"RF_JAMMING_DIRECTIONAL", "GNSS_SPOOFING_DEFENSE", "ACOUSTIC_SIREN", "ATC_NOTIFY"}
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Choose from {sorted(valid_actions)}")

    engagement = {
        "action_id": f"act_{uuid4().hex[:8]}",
        "action_type": action,
        "target_track_id": target_track_id,
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "status": "ENGAGED",
        "power_output_dbm": 43.0 if "JAMMING" in action else None,
        "estimated_efficacy": 94.5 if "JAMMING" in action else 99.0
    }

    _active_countermeasures.append(engagement)
    if len(_active_countermeasures) > 5:
        _active_countermeasures.pop(0)

    # Append to log
    with COUNTERMEASURES_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(engagement) + "\n")

    return {
        "status": "success",
        "message": f"Countermeasure {action} dispatched against Track {target_track_id or 'ALL'}.",
        "engagement": engagement
    }


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


@app.get("/report/csv")
def report_csv():
    alerts = load_alerts(LOG_PATH)
    csv_data = build_csv_report(alerts)
    filename = f"drone_threat_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/report/json")
def report_json():
    alerts = load_alerts(LOG_PATH)
    json_data = build_json_export(alerts)
    filename = f"drone_threat_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    return Response(
        content=json_data,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


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
