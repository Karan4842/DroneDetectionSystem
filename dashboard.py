from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import streamlit as st


LOG_PATH = Path("outputs/logs/alerts.jsonl")


def load_alerts(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []

    alerts = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        alerts.append(json.loads(line))
    return alerts


def summarize_alerts(alerts: list[dict]) -> dict:
    track_counter = Counter()
    severity_counter = Counter()
    zone_counter = Counter()

    for event in alerts:
        for alert in event.get("alerts", []):
            if alert.get("track_id") is not None:
                track_counter[str(alert["track_id"])] += 1
            severity_counter[alert.get("severity", "unknown")] += 1
            for zone_name in alert.get("violated_zones", []):
                zone_counter[zone_name] += 1

    return {
        "event_count": len(alerts),
        "unique_tracks": len(track_counter),
        "severity_counter": severity_counter,
        "zone_counter": zone_counter,
    }


def render_summary(summary: dict) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("Alert Events", summary["event_count"])
    col2.metric("Tracked Threats", summary["unique_tracks"])
    col3.metric("Critical Alerts", summary["severity_counter"].get("critical", 0))


def render_charts(summary: dict) -> None:
    st.subheader("Threat Severity Distribution")
    if summary["severity_counter"]:
        st.bar_chart(dict(summary["severity_counter"]))
    else:
        st.info("No severity data available yet.")

    st.subheader("Restricted Zone Violations")
    if summary["zone_counter"]:
        st.bar_chart(dict(summary["zone_counter"]))
    else:
        st.info("No restricted-zone entries logged yet.")


def render_event_feed(alerts: list[dict]) -> None:
    st.subheader("Recent Alert Feed")
    if not alerts:
        st.info("No alert events have been logged yet.")
        return

    for event in reversed(alerts[-10:]):
        with st.expander(
            f"{event['timestamp_utc']} | {event['site_name']} | {event['event_id']}",
            expanded=False,
        ):
            st.write(f"Source: `{event.get('source', 'unknown')}`")
            st.write(f"Human review required: `{event.get('human_review_required', True)}`")

            evidence_frame = event.get("evidence_frame")
            if evidence_frame:
                evidence_path = Path(evidence_frame)
                if evidence_path.exists():
                    st.image(str(evidence_path), caption=evidence_path.name)

            for alert in event.get("alerts", []):
                st.json(alert)


def main() -> None:
    st.set_page_config(page_title="Drone Threat Dashboard", layout="wide")
    st.title("Drone Threat Monitoring Dashboard")
    st.caption("SRS-aligned monitoring view for real-time alert review and post-incident analysis.")

    alerts = load_alerts(LOG_PATH)
    summary = summarize_alerts(alerts)

    render_summary(summary)
    render_charts(summary)
    render_event_feed(alerts)


if __name__ == "__main__":
    main()
