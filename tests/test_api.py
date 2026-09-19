from fastapi.testclient import TestClient
import pytest
from api import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "2.0.0"


def test_config_endpoint():
    response = client.get("/config")
    assert response.status_code == 200
    data = response.json()
    assert "site_name" in data
    assert "restricted_zones" in data


def test_summary_endpoint():
    response = client.get("/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_events" in data
    assert "runtime" in data


def test_sensors_telemetry_endpoint():
    response = client.get("/sensors/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "radar_tracks" in data
    assert "rf_signals" in data
    assert "acoustic_telemetry" in data


def test_countermeasures_status_endpoint():
    response = client.get("/countermeasures/status")
    assert response.status_code == 200
    data = response.json()
    assert "active_engagements" in data


def test_trigger_countermeasure_valid():
    response = client.post("/countermeasures/trigger?action=RF_JAMMING_DIRECTIONAL&target_track_id=1")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["engagement"]["action_type"] == "RF_JAMMING_DIRECTIONAL"


def test_trigger_countermeasure_invalid():
    response = client.post("/countermeasures/trigger?action=INVALID_ACTION")
    assert response.status_code == 400


def test_report_endpoints():
    res_text = client.get("/report")
    assert res_text.status_code == 200
    assert "DRONE THREAT COMMAND SYSTEM" in res_text.text

    res_csv = client.get("/report/csv")
    assert res_csv.status_code == 200
    assert "Event_ID,Timestamp_UTC" in res_csv.text

    res_json = client.get("/report/json")
    assert res_json.status_code == 200
