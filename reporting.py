from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def load_alerts(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []

    alerts = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            alerts.append(json.loads(line))
    return alerts


def build_text_report(alerts: list[dict]) -> str:
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

    lines = [
        "Drone Detection System Report",
        f"Total alert events: {len(alerts)}",
        f"Unique tracks: {len(track_counter)}",
        f"Critical alerts: {severity_counter.get('critical', 0)}",
        f"High alerts: {severity_counter.get('high', 0)}",
        f"Medium alerts: {severity_counter.get('medium', 0)}",
        f"Low alerts: {severity_counter.get('low', 0)}",
        "",
        "Hourly activity:",
    ]

    if hourly_counter:
        for hour_label, count in sorted(hourly_counter.items()):
            lines.append(f"- {hour_label}: {count}")
    else:
        lines.append("- No timestamps available")

    lines.extend([
        "",
        "Restricted-zone activity:",
    ])

    if zone_counter:
        for zone_name, count in zone_counter.most_common():
            lines.append(f"- {zone_name}: {count}")
    else:
        lines.append("- No zone intrusions logged")

    return "\n".join(lines)


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
