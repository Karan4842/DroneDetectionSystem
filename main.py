from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

os.environ.setdefault("YOLO_CONFIG_DIR", "outputs")

import cv2
from ultralytics import YOLO

from security import (
    append_alert_log,
    build_alert_event,
    draw_status_banner,
    enrich_detections,
    ensure_output_dir,
    extract_detections,
    load_config,
    normalize_classes,
    resolve_model_source,
    save_alert_frame,
    save_frame,
    save_latest_frame,
    write_runtime_status,
)
from tracker import CentroidTracker


WINDOW_NAME = "Drone Detection System"
BASE_DIR = Path(__file__).resolve().parent


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run drone threat monitoring on an image, video file, or webcam stream."
    )
    parser.add_argument(
        "--config",
        default=str(BASE_DIR / "security_config.json"),
        help="Path to the security configuration JSON file.",
    )
    parser.add_argument(
        "--source",
        default="0",
        help="Input source. Use webcam index like 0, or provide an image/video path.",
    )
    parser.add_argument(
        "--model",
        default=str(BASE_DIR.parent / "yolov8n.pt"),
        help="YOLO model path or model name supported by Ultralytics.",
    )
    parser.add_argument(
        "--classes",
        nargs="*",
        default=[],
        help="Optional class names to monitor. Example: --classes drone airplane helicopter",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Minimum confidence threshold for detections.",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save annotated frames to the outputs folder.",
    )
    parser.add_argument(
        "--show-labels",
        action="store_true",
        help="Draw class names, confidence, and track IDs on detections.",
    )
    return parser


def resolve_source(source: str) -> int | str:
    if source.isdigit():
        return int(source)

    source_path = Path(source)
    candidate_paths = [
        source_path,
        BASE_DIR / source_path,
        BASE_DIR.parent / source_path,
    ]

    for candidate in candidate_paths:
        if candidate.exists():
            return str(candidate.resolve())

    raise FileNotFoundError(
        f"Source not found: {source}. Put the image or video inside the project and pass its path."
    )


def is_image_source(source: int | str) -> bool:
    if isinstance(source, int):
        return False

    return Path(source).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def filter_alerts(detections: list[dict], alert_threshold: int) -> list[dict]:
    return [item for item in detections if item["risk_score"] >= alert_threshold]


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    source = resolve_source(args.source)
    model = YOLO(resolve_model_source(args.model))
    tracker = CentroidTracker(
        max_distance=float(config["tracking_thresholds"]["max_distance_pixels"]),
        max_missed_frames=int(config["tracking_thresholds"]["max_missed_frames"]),
    )
    watched_classes = normalize_classes(args.classes) or normalize_classes(
        config.get("suspicious_classes", [])
    )
    show_labels = args.show_labels or config.get("show_labels", False)
    output_dir = ensure_output_dir() if (args.save or config.get("save_all_frames")) else None
    alerts_dir = ensure_output_dir("outputs/alerts")
    logs_dir = ensure_output_dir("outputs/logs")
    live_dir = ensure_output_dir("outputs/live")
    alert_log_path = logs_dir / "alerts.jsonl"
    runtime_status_path = logs_dir / "runtime_status.json"
    cooldown_seconds = int(config.get("alert_cooldown_seconds", 15))
    last_alert_by_track: dict[int, float] = {}

    if watched_classes:
        available_names = {str(name).lower() for name in model.names.values()}
        missing_classes = sorted(name for name in watched_classes if name not in available_names)
        if missing_classes:
            print(
                "Warning: these classes are not present in the loaded model: "
                + ", ".join(missing_classes)
            )
            print("The monitor will only draw boxes for classes the model actually supports.")

    frame_index = 0
    stream = model.predict(
        source=source,
        stream=True,
        conf=max(args.conf, float(config["confidence_thresholds"]["detection"])),
        verbose=False,
    )
    image_mode = is_image_source(source)

    for result in stream:
        frame = result.orig_img.copy()
        raw_detections = extract_detections(result, watched_classes)
        tracker.update(raw_detections, frame_index)
        detections = enrich_detections(
            frame=frame,
            detections=raw_detections,
            tracker_tracks=tracker.tracks,
            show_labels=show_labels,
            config=config,
        )
        alerts = filter_alerts(detections, int(config["alert_threshold"]))
        active_alerts = 0
        current_time = time.time()

        for alert in alerts:
            track_id = alert.get("track_id")
            if track_id is None:
                continue

            if (current_time - last_alert_by_track.get(track_id, 0.0)) < cooldown_seconds:
                continue

            active_alerts += 1
            evidence_path = None
            if config.get("save_alert_frames", True):
                event_id = f"track_{track_id}_frame_{frame_index:06d}"
                evidence_path = save_alert_frame(frame, alerts_dir, event_id)

            alert_event = build_alert_event(
                site_name=config["site_name"],
                source=str(args.source),
                alerts=[alert],
                frame_index=frame_index,
                evidence_path=evidence_path,
            )
            append_alert_log(alert_log_path, alert_event)
            print(
                f"[ALERT] Track {track_id} classified as {alert['severity']} risk at "
                f"{config['site_name']}."
            )
            last_alert_by_track[track_id] = current_time

        draw_status_banner(
            frame=frame,
            site_name=config["site_name"],
            active_alerts=active_alerts,
            active_tracks=len(tracker.tracks),
        )
        cv2.imshow(WINDOW_NAME, frame)

        if output_dir is not None:
            save_frame(frame, output_dir, frame_index)

        latest_frame_path = save_latest_frame(frame, live_dir)

        write_runtime_status(
            runtime_status_path,
            {
                "running": True,
                "site_name": config["site_name"],
                "source": str(args.source),
                "resolved_source": str(source),
                "frame_index": frame_index,
                "active_tracks": len(tracker.tracks),
                "active_alerts": active_alerts,
                "last_updated_epoch": time.time(),
                "last_updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "latest_frame_url": f"/live/{latest_frame_path.name}",
                "latest_detections": detections[-5:],
                "image_mode": image_mode,
            },
        )

        frame_index += 1
        key = cv2.waitKey(0 if image_mode else 1) & 0xFF
        if key in (27, ord("q")):
            break

        if image_mode:
            break

    write_runtime_status(
        runtime_status_path,
        {
            "running": False,
            "site_name": config["site_name"],
            "source": str(args.source),
            "resolved_source": str(source),
            "frame_index": frame_index,
            "active_tracks": 0,
            "active_alerts": 0,
            "last_updated_epoch": time.time(),
            "last_updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "latest_frame_url": f"/live/latest.jpg" if live_dir.joinpath("latest.jpg").exists() else None,
            "latest_detections": [],
            "image_mode": image_mode,
        },
    )

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
