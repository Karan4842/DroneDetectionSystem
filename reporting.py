from __future__ import annotations

from collections import Counter
import csv
from datetime import datetime
import io
import json
from pathlib import Path


def load_alerts(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []

    alerts = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                alerts.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return alerts


def build_text_report(alerts: list[dict]) -> str:
    severity_counter = Counter()
    zone_counter = Counter()
    track_counter = Counter()
    hourly_counter = Counter()
    class_counter = Counter()

    for event in alerts:
        timestamp_value = event.get("timestamp_utc")
        if timestamp_value:
            try:
                hourly_counter[
                    datetime.strptime(timestamp_value, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:00 UTC")
                ] += 1
            except ValueError:
                pass
        for alert in event.get("alerts", []):
            severity = alert.get("severity", "unknown")
            severity_counter[severity] += 1
            class_counter[alert.get("class_name", "unknown")] += 1
            track_id = alert.get("track_id")
            if track_id is not None:
                track_counter[str(track_id)] += 1
            for zone_name in alert.get("violated_zones", []):
                zone_counter[zone_name] += 1

    lines = [
        "============================================================",
        "          DRONE THREAT COMMAND SYSTEM - INCIDENT REPORT     ",
        "============================================================",
        f"Generated UTC       : {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"Total Alert Events  : {len(alerts)}",
        f"Unique Tracks       : {len(track_counter)}",
        f"Critical Incidents  : {severity_counter.get('critical', 0)}",
        f"High Risk Alerts    : {severity_counter.get('high', 0)}",
        f"Medium Risk Alerts  : {severity_counter.get('medium', 0)}",
        f"Low Risk Alerts     : {severity_counter.get('low', 0)}",
        "------------------------------------------------------------",
        "DETECTED TARGET CLASSES:",
    ]

    if class_counter:
        for cls_name, count in class_counter.most_common():
            lines.append(f"  - {cls_name.upper():<16}: {count} occurrences")
    else:
        lines.append("  - No target classes recorded")

    lines.extend([
        "------------------------------------------------------------",
        "RESTRICTED ZONE INTRUSIONS:",
    ])

    if zone_counter:
        for zone_name, count in zone_counter.most_common():
            lines.append(f"  - {zone_name:<20}: {count} breaches")
    else:
        lines.append("  - No zone breaches logged")

    lines.extend([
        "------------------------------------------------------------",
        "HOURLY ACTIVITY DISTRIBUTION:",
    ])

    if hourly_counter:
        for hour_label, count in sorted(hourly_counter.items()):
            lines.append(f"  - {hour_label}: {count} events")
    else:
        lines.append("  - No timestamps available")

    lines.append("============================================================")
    return "\n".join(lines)


def build_csv_report(alerts: list[dict]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Event_ID",
        "Timestamp_UTC",
        "Site_Name",
        "Source",
        "Track_ID",
        "Class_Name",
        "Confidence",
        "Risk_Score",
        "Severity",
        "Estimated_Speed_px_frame",
        "Violated_Zones",
        "Evidence_Frame",
        "Human_Review_Required"
    ])

    for event in alerts:
        event_id = event.get("event_id", "")
        ts = event.get("timestamp_utc", "")
        site = event.get("site_name", "")
        src = event.get("source", "")
        evidence = event.get("evidence_frame", "")
        review = event.get("human_review_required", True)

        alert_list = event.get("alerts", [])
        if not alert_list:
            writer.writerow([event_id, ts, site, src, "", "", "", "", "", "", "", evidence, review])
        else:
            for alert in alert_list:
                writer.writerow([
                    event_id,
                    ts,
                    site,
                    src,
                    alert.get("track_id", ""),
                    alert.get("class_name", ""),
                    alert.get("confidence", ""),
                    alert.get("risk_score", ""),
                    alert.get("severity", ""),
                    alert.get("estimated_speed", ""),
                    "; ".join(alert.get("violated_zones", [])),
                    evidence,
                    review
                ])

    return output.getvalue()


def build_json_export(alerts: list[dict]) -> str:
    return json.dumps(alerts, indent=2)


def build_alert_analytics(alerts: list[dict]) -> dict:
    severity_counter = Counter()
    zone_counter = Counter()
    track_counter = Counter()
    hourly_counter = Counter()

    for event in alerts:
        timestamp_value = event.get("timestamp_utc")
        if timestamp_value:
            try:
                hourly_counter[
                    datetime.strptime(timestamp_value, "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:00 UTC")
                ] += 1
            except ValueError:
                pass

        for alert in event.get("alerts", []):
            severity_counter[alert.get("severity", "unknown")] += 1
            track_id = alert.get("track_id")
            if track_id is not None:
                track_counter[str(track_id)] += 1
            for zone_name in alert.get("violated_zones", []):
                zone_counter[zone_name] += 1

    hourly_series = [
        {"label": hour_label, "count": count}
        for hour_label, count in sorted(hourly_counter.items())
    ]

    if len(hourly_series) > 8:
        hourly_series = hourly_series[-8:]

    return {
        "event_count": len(alerts),
        "unique_tracks": len(track_counter),
        "severity_breakdown": dict(severity_counter),
        "zone_breakdown": dict(zone_counter),
        "top_tracks": track_counter.most_common(5),
        "hourly_series": hourly_series,
        "last_event_timestamp": alerts[-1].get("timestamp_utc") if alerts else None,
    }
