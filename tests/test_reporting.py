import pytest
from reporting import (
    build_alert_analytics,
    build_csv_report,
    build_json_export,
    build_text_report,
)


@pytest.fixture
def sample_alerts():
    return [
        {
            "event_id": "alert_20260916T120000Z_000001",
            "timestamp_utc": "20260916T120000Z",
            "site_name": "Perimeter Gate A",
            "source": "0",
            "evidence_frame": "outputs/alerts/alert_01.jpg",
            "human_review_required": True,
            "alerts": [
                {
                    "track_id": 1,
                    "class_name": "drone",
                    "confidence": 0.92,
                    "risk_score": 90,
                    "severity": "critical",
                    "estimated_speed": 15.2,
                    "violated_zones": ["Runway Approach"]
                }
            ]
        }
    ]


def test_build_text_report(sample_alerts):
    report_text = build_text_report(sample_alerts)
    assert "DRONE THREAT COMMAND SYSTEM - INCIDENT REPORT" in report_text
    assert "Critical Incidents  : 1" in report_text
    assert "Runway Approach" in report_text


def test_build_csv_report(sample_alerts):
    csv_text = build_csv_report(sample_alerts)
    assert "Event_ID,Timestamp_UTC,Site_Name" in csv_text
    assert "alert_20260916T120000Z_000001" in csv_text
    assert "drone" in csv_text
    assert "critical" in csv_text


def test_build_json_export(sample_alerts):
    json_text = build_json_export(sample_alerts)
    assert '"event_id": "alert_20260916T120000Z_000001"' in json_text


def test_build_alert_analytics(sample_alerts):
    analytics = build_alert_analytics(sample_alerts)
    assert analytics["event_count"] == 1
    assert analytics["unique_tracks"] == 1
    assert analytics["severity_breakdown"]["critical"] == 1
    assert analytics["zone_breakdown"]["Runway Approach"] == 1
