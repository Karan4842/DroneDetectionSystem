from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import random
from typing import Iterable

import cv2

from tracker import compute_center, euclidean_distance


BASE_DIR = Path(__file__).resolve().parent


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)


def save_config(config: dict, config_path: str) -> None:
    with open(config_path, "w", encoding="utf-8") as config_file:
        json.dump(config, config_file, indent=2)


def ensure_output_dir(base_dir: str = "outputs") -> Path:
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def normalize_classes(raw_classes: Iterable[str]) -> set[str]:
    return {name.strip().lower() for name in raw_classes if name.strip()}


def resolve_model_source(model_source: str) -> str:
    source_path = Path(model_source)
    candidate_paths = [
        source_path,
        BASE_DIR / source_path,
        BASE_DIR.parent / source_path,
    ]

    for candidate in candidate_paths:
        if candidate.exists():
            return str(candidate.resolve())

    return model_source


def to_absolute_zone(zone: dict, frame_width: int, frame_height: int) -> tuple[int, int, int, int]:
    return (
        int(zone["x1"] * frame_width),
        int(zone["y1"] * frame_height),
        int(zone["x2"] * frame_width),
        int(zone["y2"] * frame_height),
    )


def box_intersects_zone(box_coords: tuple[int, int, int, int], zone_coords: tuple[int, int, int, int]) -> bool:
    bx1, by1, bx2, by2 = box_coords
    zx1, zy1, zx2, zy2 = zone_coords
    return bx1 < zx2 and bx2 > zx1 and by1 < zy2 and by2 > zy1


def direction_to_zone(
    box_coords: tuple[int, int, int, int],
    current_center: tuple[float, float],
    previous_center: tuple[float, float] | None,
    zone_coords: tuple[int, int, int, int],
) -> bool:
    if previous_center is None:
        return False

    zx1, zy1, zx2, zy2 = zone_coords
    zone_center = ((zx1 + zx2) / 2.0, (zy1 + zy2) / 2.0)
    previous_distance = euclidean_distance(previous_center, zone_center)
    current_distance = euclidean_distance(current_center, zone_center)
    return current_distance < previous_distance


def calculate_risk_score(
    confidence: float,
    box_area_ratio: float,
    in_restricted_zone: bool,
    track_age_frames: int,
    estimated_speed: float,
    moving_towards_zone: bool,
    config: dict,
    rf_confidence: float = 0.0,
    radar_detected: bool = False,
) -> int:
    weights = config["risk_weights"]
    thresholds = config["confidence_thresholds"]
    score = weights["base_detection"]

    if in_restricted_zone:
        score += weights["zone_intrusion"]
    if confidence >= thresholds["high"]:
        score += weights["high_confidence_bonus"]
    if box_area_ratio >= config["size_thresholds"]["large_object_ratio"]:
        score += weights["large_object_bonus"]
    if track_age_frames >= config["tracking_thresholds"]["loitering_frames"]:
        score += weights["loitering_bonus"]
    if estimated_speed >= config["tracking_thresholds"]["fast_movement_pixels"]:
        score += weights["speed_bonus"]
    if moving_towards_zone:
        score += weights["approach_bonus"]

    # Sensor Fusion Bonus
    if rf_confidence > 0.6:
        score += 10
    if radar_detected:
        score += 10

    return min(score, 100)


def severity_from_score(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def draw_detection(
    frame,
    box_coords: tuple[int, int, int, int],
    class_name: str,
    confidence: float,
    track_id: int | None,
    show_labels: bool,
    severity: str,
) -> None:
    x1, y1, x2, y2 = box_coords
    colors = {
        "low": (0, 200, 255),
        "medium": (0, 255, 255),
        "high": (0, 140, 255),
        "critical": (0, 0, 255),
    }
    color = colors.get(severity, (0, 255, 0))
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

    if show_labels:
        track_label = f"ID:{track_id} " if track_id is not None else ""
        label = f"{track_label}{class_name} {confidence:.2f} {severity.upper()}"
        cv2.putText(
            frame,
            label,
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )


def draw_restricted_zones(frame, zones: list[dict]) -> None:
    frame_height, frame_width = frame.shape[:2]
    for zone in zones:
        x1, y1, x2, y2 = to_absolute_zone(zone, frame_width, frame_height)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (50, 50, 220), 2)
        cv2.putText(
            frame,
            zone["name"],
            (x1, max(y1 - 10, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (50, 50, 220),
            2,
            cv2.LINE_AA,
        )


def draw_status_banner(frame, site_name: str, active_alerts: int, active_tracks: int) -> None:
    banner_text = (
        f"{site_name} | AI Monitor | Active alerts: {active_alerts} | "
        f"Tracks: {active_tracks}"
    )
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), (20, 20, 20), -1)
    cv2.putText(
        frame,
        banner_text,
        (10, 26),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def extract_detections(result, watched_classes: set[str]) -> list[dict]:
    names = result.names
    detections = []
    for box in result.boxes:
        class_id = int(box.cls[0].item())
        class_name = str(names[class_id]).lower()
        confidence = float(box.conf[0].item())

        if watched_classes and class_name not in watched_classes:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        detections.append(
            {
                "class_name": class_name,
                "confidence": round(confidence, 4),
                "box": (x1, y1, x2, y2),
            }
        )
    return detections


def enrich_detections(
    frame,
    detections: list[dict],
    tracker_tracks: dict[int, object],
    show_labels: bool,
    config: dict,
) -> list[dict]:
    frame_height, frame_width = frame.shape[:2]
    frame_area = max(frame_height * frame_width, 1)
    zones = config.get("restricted_zones", [])
    enriched = []

    draw_restricted_zones(frame, zones)

    for detection in detections:
        x1, y1, x2, y2 = detection["box"]
        box_area_ratio = max((x2 - x1) * (y2 - y1), 0) / frame_area
        current_center = compute_center(detection["box"])
        track = tracker_tracks.get(detection["track_id"])
        previous_center = track.history[-2] if track and len(track.history) >= 2 else None
        violated_zones = []
        moving_towards_zone = False

        for zone in zones:
            zone_coords = to_absolute_zone(zone, frame_width, frame_height)
            if box_intersects_zone(detection["box"], zone_coords):
                violated_zones.append(zone["name"])
            moving_towards_zone = moving_towards_zone or direction_to_zone(
                box_coords=detection["box"],
                current_center=current_center,
                previous_center=previous_center,
                zone_coords=zone_coords,
            )

        risk_score = calculate_risk_score(
            confidence=detection["confidence"],
            box_area_ratio=box_area_ratio,
            in_restricted_zone=bool(violated_zones),
            track_age_frames=detection.get("track_age_frames", 1),
            estimated_speed=detection.get("estimated_speed", 0.0),
            moving_towards_zone=moving_towards_zone,
            config=config,
        )
        severity = severity_from_score(risk_score)
        draw_detection(
            frame=frame,
            box_coords=detection["box"],
            class_name=detection["class_name"],
            confidence=detection["confidence"],
            track_id=detection.get("track_id"),
            show_labels=show_labels,
            severity=severity,
        )
        enriched.append(
            {
                "track_id": detection.get("track_id"),
                "class_name": detection["class_name"],
                "confidence": detection["confidence"],
                "box": list(detection["box"]),
                "risk_score": risk_score,
                "severity": severity,
                "violated_zones": violated_zones,
                "track_age_frames": detection.get("track_age_frames", 1),
                "estimated_speed": detection.get("estimated_speed", 0.0),
                "moving_towards_zone": moving_towards_zone,
            }
        )

    return enriched


def generate_sensor_telemetry(detections: list[dict], site_name: str, config: dict) -> dict:
    """
    Multi-sensor fusion simulator:
    Combines optical bounding box coordinates with simulated RF frequency analysis,
    Radar azimuth/distance, and acoustic harmonic signatures.
    """
    radar_tracks = []
    rf_signals = []
    protocols = ["DJI OcuSync 3.0", "Autel SkyLink", "ExpressLRS 2.4G", "Analog Video 5.8G", "Custom FPV"]

    for det in detections:
        track_id = det.get("track_id", 1)
        box = det.get("box", [100, 100, 200, 200])
        cx, cy = (box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0

        # Radar calculation (polar coordinates mapped from visual center)
        azimuth_deg = round((cx / 640.0) * 120.0 - 60.0, 1)  # -60 to +60 deg FOV
        distance_m = round(max(30.0, 1200.0 - (cy * 1.5)), 1) # closer at bottom
        elevation_deg = round(max(5.0, 45.0 - (cy / 640.0) * 35.0), 1)
        rcs_m2 = round(0.01 + (det.get("confidence", 0.5) * 0.05), 3) # small UAV RCS

        radar_tracks.append({
            "track_id": track_id,
            "azimuth_deg": azimuth_deg,
            "range_meters": distance_m,
            "elevation_deg": elevation_deg,
            "velocity_mps": round(det.get("estimated_speed", 5.0) * 0.8, 1),
            "rcs_m2": rcs_m2,
            "threat_level": det.get("severity", "low")
        })

        # RF Telemetry calculation
        rf_freq = 2412 + (track_id * 15) % 80 if (track_id % 2 == 0) else 5745 + (track_id * 20) % 120
        rf_signals.append({
            "track_id": track_id,
            "frequency_mhz": rf_freq,
            "rssi_dbm": round(-45 - (distance_m / 25.0), 1),
            "protocol": protocols[track_id % len(protocols)],
            "remote_id_broadcast": bool(track_id % 3 == 0),
            "signal_snr_db": round(24.5 - (distance_m / 60.0), 1)
        })

    # Global acoustic noise floor
    acoustic_signature = {
        "blade_pass_freq_hz": 180 + int(random.random() * 40) if detections else 0,
        "acoustic_snr_db": 12.4 if detections else 2.1,
        "drone_audio_match": bool(detections and len(detections) > 0)
    }

    return {
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "site_name": site_name,
        "sensors_active": {
            "optical_camera": config.get("sensor_stack", {}).get("camera_enabled", True),
            "pulse_doppler_radar": config.get("sensor_stack", {}).get("radar_enabled", True),
            "rf_spectrum_analyzer": config.get("sensor_stack", {}).get("rf_sensor_enabled", True),
            "acoustic_array": True
        },
        "radar_tracks": radar_tracks,
        "rf_signals": rf_signals,
        "acoustic_telemetry": acoustic_signature,
        "fused_threat_count": len(detections)
    }


def save_frame(frame, output_dir: Path, frame_index: int) -> None:
    output_path = output_dir / f"frame_{frame_index:06d}.jpg"
    cv2.imwrite(str(output_path), frame)


def save_latest_frame(frame, live_dir: Path) -> Path:
    output_path = live_dir / "latest.jpg"
    cv2.imwrite(str(output_path), frame)
    return output_path


def save_alert_frame(frame, alerts_dir: Path, event_id: str) -> Path:
    output_path = alerts_dir / f"{event_id}.jpg"
    cv2.imwrite(str(output_path), frame)
    return output_path


def append_alert_log(log_path: Path, event: dict) -> None:
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event) + "\n")


def write_runtime_status(status_path: Path, payload: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_alert_event(
    site_name: str,
    source: str,
    alerts: list[dict],
    frame_index: int,
    evidence_path: Path | None,
) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    event_id = f"alert_{timestamp}_{frame_index:06d}"
    return {
        "event_id": event_id,
        "timestamp_utc": timestamp,
        "site_name": site_name,
        "source": source,
        "alerts": alerts,
        "evidence_frame": str(evidence_path) if evidence_path else None,
        "human_review_required": True,
    }
