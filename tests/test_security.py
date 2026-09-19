import pytest
from security import (
    box_intersects_zone,
    calculate_risk_score,
    generate_sensor_telemetry,
    normalize_classes,
    severity_from_score,
    to_absolute_zone,
)


def test_normalize_classes():
    raw = [" Drone ", "AIRPLANE", "", "helicopter "]
    normalized = normalize_classes(raw)
    assert normalized == {"drone", "airplane", "helicopter"}


def test_to_absolute_zone():
    zone = {"name": "TestZone", "x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6}
    abs_zone = to_absolute_zone(zone, frame_width=1000, frame_height=500)
    assert abs_zone == (100, 100, 500, 300)


def test_box_intersects_zone():
    zone_coords = (100, 100, 300, 300)
    inside_box = (150, 150, 200, 200)
    outside_box = (400, 400, 500, 500)

    assert box_intersects_zone(inside_box, zone_coords) is True
    assert box_intersects_zone(outside_box, zone_coords) is False


def test_calculate_risk_score_and_severity():
    config = {
        "risk_weights": {
            "base_detection": 35,
            "zone_intrusion": 45,
            "high_confidence_bonus": 10,
            "large_object_bonus": 10,
            "loitering_bonus": 10,
            "speed_bonus": 8,
            "approach_bonus": 12
        },
        "confidence_thresholds": {
            "detection": 0.3,
            "high": 0.7
        },
        "size_thresholds": {
            "large_object_ratio": 0.08
        },
        "tracking_thresholds": {
            "loitering_frames": 30,
            "fast_movement_pixels": 35
        }
    }

    # Low risk scenario
    score_low = calculate_risk_score(
        confidence=0.5,
        box_area_ratio=0.01,
        in_restricted_zone=False,
        track_age_frames=5,
        estimated_speed=2.0,
        moving_towards_zone=False,
        config=config,
    )
    assert score_low == 35
    assert severity_from_score(score_low) == "low"

    # Critical breach scenario
    score_critical = calculate_risk_score(
        confidence=0.9,
        box_area_ratio=0.1,
        in_restricted_zone=True,
        track_age_frames=40,
        estimated_speed=40.0,
        moving_towards_zone=True,
        config=config,
    )
    assert score_critical == 100
    assert severity_from_score(score_critical) == "critical"


def test_generate_sensor_telemetry():
    detections = [
        {
            "track_id": 1,
            "class_name": "drone",
            "confidence": 0.85,
            "box": [100, 100, 200, 200],
            "severity": "critical",
            "estimated_speed": 12.5
        }
    ]
    telemetry = generate_sensor_telemetry(
        detections=detections,
        site_name="Airport Runway",
        config={"sensor_stack": {"camera_enabled": True, "radar_enabled": True, "rf_sensor_enabled": True}}
    )

    assert telemetry["site_name"] == "Airport Runway"
    assert len(telemetry["radar_tracks"]) == 1
    assert telemetry["radar_tracks"][0]["track_id"] == 1
    assert len(telemetry["rf_signals"]) == 1
    assert telemetry["rf_signals"][0]["track_id"] == 1
    assert telemetry["acoustic_telemetry"]["drone_audio_match"] is True
