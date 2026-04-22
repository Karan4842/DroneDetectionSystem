import { useEffect, useMemo, useState } from "react";

const refreshMs = 5000;
const fallbackText = "Not available";

const timestampFormatter = new Intl.DateTimeFormat("en-US", {
  dateStyle: "medium",
  timeStyle: "short"
});

const relativeFormatter = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

const fetchJson = async (url) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed for ${url}`);
  }
  return response.json();
};

function parseCompactUtc(value) {
  if (!value || typeof value !== "string") {
    return null;
  }

  const match = value.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (!match) {
    return null;
  }

  const [, year, month, day, hour, minute, second] = match;
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second));
}

function formatTimestamp(value) {
  const parsed = parseCompactUtc(value);
  if (!parsed) {
    return value ?? fallbackText;
  }
  return timestampFormatter.format(parsed);
}

function formatRelative(value) {
  const parsed = parseCompactUtc(value);
  if (!parsed) {
    return fallbackText;
  }

  const deltaSeconds = Math.round((parsed.getTime() - Date.now()) / 1000);
  const absSeconds = Math.abs(deltaSeconds);

  if (absSeconds < 60) {
    return relativeFormatter.format(deltaSeconds, "second");
  }
  if (absSeconds < 3600) {
    return relativeFormatter.format(Math.round(deltaSeconds / 60), "minute");
  }
  if (absSeconds < 86400) {
    return relativeFormatter.format(Math.round(deltaSeconds / 3600), "hour");
  }
  return relativeFormatter.format(Math.round(deltaSeconds / 86400), "day");
}

function getInitialPage() {
  if (typeof window === "undefined") {
    return "overview";
  }

  const page = new URLSearchParams(window.location.search).get("page");
  return ["overview", "live", "incidents", "analytics", "demo"].includes(page) ? page : "overview";
}

function getInitialPresentationMode() {
  if (typeof window === "undefined") {
    return false;
  }

  const value = new URLSearchParams(window.location.search).get("presentation");
  return value === "1" || value === "true";
}

function getInitialSelectedEventId() {
  if (typeof window === "undefined") {
    return "";
  }

  return new URLSearchParams(window.location.search).get("incident") || "";
}

function getViewportHint() {
  if (typeof window === "undefined") {
    return { scroll: 0, focus: "" };
  }

  const params = new URLSearchParams(window.location.search);
  return {
    scroll: Number(params.get("scroll") || 0),
    focus: params.get("focus") || ""
  };
}

function riskBand(score) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  if (value >= 85) return "critical";
  if (value >= 70) return "high";
  if (value >= 50) return "medium";
  return "low";
}

function StatCard({ label, value, tone, detail }) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value}</strong>
      {detail ? <span className="stat-card__detail">{detail}</span> : null}
    </div>
  );
}

function SectionHeader({ eyebrow, title, meta, action }) {
  return (
    <div className="section-header">
      <div>
        {eyebrow ? <p className="section-header__eyebrow">{eyebrow}</p> : null}
        <h3>{title}</h3>
      </div>
      <div className="section-header__meta">
        {meta ? <span>{meta}</span> : null}
        {action}
      </div>
    </div>
  );
}

function SensorPill({ label, enabled }) {
  return (
    <span className={`status-pill ${enabled ? "status-pill--on" : "status-pill--off"}`}>
      {label}: {enabled ? "online" : "offline"}
    </span>
  );
}

function MetricList({ items, emptyText }) {
  const entries = Object.entries(items || {}).sort((a, b) => b[1] - a[1]);
  const highest = Math.max(1, ...entries.map(([, value]) => Number(value) || 0));

  if (entries.length === 0) {
    return <p className="muted">{emptyText}</p>;
  }

  return (
    <div className="bar-list">
      {entries.map(([key, value]) => {
        const width = Math.max(8, ((Number(value) || 0) / highest) * 100);
        return (
          <div key={key} className="bar-row">
            <div className="bar-row__copy">
              <span>{key}</span>
              <strong>{value}</strong>
            </div>
            <div className="bar-track" aria-hidden="true">
              <span className="bar-track__fill" style={{ width: `${width}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RuntimePanel({ runtime, detectorStatus, onStartCamera, onStopCamera, busy }) {
  const detections = runtime?.latest_detections || [];
  const statusRunning = detectorStatus?.running ?? runtime?.running ?? false;
  const isManaged = detectorStatus?.managed_by_api ?? false;
  const runtimeSource = runtime?.source ?? "Not running";
  const liveFrameUrl = runtime?.latest_frame_url
    ? `${runtime.latest_frame_url}?v=${runtime?.last_updated_epoch ?? Date.now()}`
    : null;

  return (
    <section className="panel panel--stack panel--runtime">
      <SectionHeader
        eyebrow="Live telemetry"
        title="Runtime Control"
        meta={runtime?.last_updated_utc ? `Updated ${formatRelative(runtime.last_updated_utc)}` : "Waiting for the first frame"}
      />

      <div className="runtime-status">
        <span className={`live-badge ${statusRunning ? "live-badge--on" : "live-badge--off"}`}>
          {statusRunning ? "Detector online" : "Detector offline"}
        </span>
        <span className="runtime-status__detail">
          {isManaged ? `Managed by API - PID ${detectorStatus?.pid ?? "n/a"}` : "Manual session"}
        </span>
      </div>

      <div className="control-row">
        <button className="control-button" type="button" onClick={onStartCamera} disabled={busy}>
          {busy ? "Starting..." : "Start Camera"}
        </button>
        <button
          className="control-button control-button--secondary"
          type="button"
          onClick={onStopCamera}
          disabled={busy}
        >
          Stop Camera
        </button>
      </div>

      <div className="runtime-grid">
        <div className="runtime-item">
          <span>Source</span>
          <strong title={runtime?.resolved_source ?? runtimeSource}>{runtimeSource}</strong>
        </div>
        <div className="runtime-item">
          <span>Frame</span>
          <strong>{runtime?.frame_index ?? 0}</strong>
        </div>
        <div className="runtime-item">
          <span>Active Tracks</span>
          <strong>{runtime?.active_tracks ?? 0}</strong>
        </div>
        <div className="runtime-item">
          <span>Active Alerts</span>
          <strong>{runtime?.active_alerts ?? 0}</strong>
        </div>
      </div>

      <div className="chip-row chip-row--wrap">
        <span className="inline-chip">{runtime?.image_mode ? "Single image mode" : "Streaming mode"}</span>
        <span className="inline-chip">
          Last update {runtime?.last_updated_utc ? formatTimestamp(runtime.last_updated_utc) : fallbackText}
        </span>
      </div>

      <div className="runtime-feed">
        <div className="runtime-feed__header">
          <h4>Latest detections</h4>
          <span>{detections.length} in frame</span>
        </div>
        <div className="live-preview">
          <div className="live-preview__header">
            <span className="inline-chip">Camera view</span>
            <span>{runtime?.running ? "Updating live" : "Awaiting detector"}</span>
          </div>
          {liveFrameUrl ? (
            <img className="live-preview__image" src={liveFrameUrl} alt="Latest detector frame" />
          ) : (
            <div className="live-preview__placeholder">
              <strong>No live frame yet</strong>
              <span>Start the detector to stream the latest annotated frame here.</span>
            </div>
          )}
        </div>
        {detections.length === 0 ? (
          <p className="muted">No live detections in the latest frame.</p>
        ) : (
          detections.map((detection, index) => {
            const severity = detection.severity || riskBand(detection.risk_score);
            const riskScore = Math.max(0, Math.min(100, Number(detection.risk_score) || 0));
            return (
              <div key={`${detection.track_id ?? "na"}-${index}`} className="runtime-detection">
                <div className="runtime-detection__top">
                  <div>
                    <strong>{detection.class_name}</strong>
                    <span>
                      Track {detection.track_id ?? "N/A"} - Age {detection.track_age_frames ?? 1} frames
                    </span>
                  </div>
                  <span className={`severity-pill severity-pill--${severity}`}>{severity}</span>
                </div>
                <div className="meter">
                  <span style={{ width: `${riskScore}%` }} />
                </div>
                <div className="runtime-detection__meta">
                  <span>Risk {riskScore}</span>
                  <span>Speed {Number(detection.estimated_speed || 0).toFixed(1)} px/frame</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </section>
  );
}

function SummaryPanel({ config, summary, runtime, detectorStatus }) {
  const sensorStack = config?.sensor_stack || {};
  const watchedClasses = config?.suspicious_classes || [];
  const zones = config?.restricted_zones || [];

  return (
    <section className="panel panel--stack">
      <SectionHeader
        eyebrow="Command posture"
        title="Operational Snapshot"
        meta={summary?.latest_event ? "Latest incident available" : "No incident history yet"}
      />

      <div className="hero-panel__stack">
        <div className="hero-panel__block">
          <span className="hero-panel__label">Protected Site</span>
          <strong>{config?.site_name ?? "Loading..."}</strong>
          <p>{runtime?.running ? "Monitoring active" : "Monitoring paused"}</p>
        </div>

        <div className="hero-panel__block">
          <span className="hero-panel__label">Detector</span>
          <strong>{detectorStatus?.running ? "Live" : "Standby"}</strong>
          <p>
            {detectorStatus?.managed_by_api
              ? `API-managed process${detectorStatus.pid ? ` - PID ${detectorStatus.pid}` : ""}`
              : "Manual launch"}
          </p>
        </div>

        <div className="hero-panel__block">
          <span className="hero-panel__label">Policy</span>
          <strong>Alert threshold {config?.alert_threshold ?? "n/a"}</strong>
          <p>Cooldown {config?.alert_cooldown_seconds ?? "n/a"} seconds</p>
        </div>
      </div>

      <div className="chip-row chip-row--wrap">
        <SensorPill label="Camera" enabled={!!sensorStack.camera_enabled} />
        <SensorPill label="Radar" enabled={!!sensorStack.radar_enabled} />
        <SensorPill label="RF" enabled={!!sensorStack.rf_sensor_enabled} />
      </div>

      <div className="runtime-grid runtime-grid--compact">
        <div className="runtime-item">
          <span>Watched Classes</span>
          <strong>{watchedClasses.length}</strong>
        </div>
        <div className="runtime-item">
          <span>Restricted Zones</span>
          <strong>{zones.length}</strong>
        </div>
        <div className="runtime-item">
          <span>Total Alerts</span>
          <strong>{summary?.total_events ?? 0}</strong>
        </div>
        <div className="runtime-item">
          <span>Critical Alerts</span>
          <strong>{summary?.critical_alerts ?? 0}</strong>
        </div>
      </div>
    </section>
  );
}

function AnalyticsPanel({ analytics }) {
  const hourlySeries = analytics?.hourly_series || [];
  const topTracks = analytics?.top_tracks || [];
  const highest = Math.max(1, ...hourlySeries.map((entry) => Number(entry.count) || 0));

  return (
    <section className="panel panel--stack">
      <SectionHeader
        eyebrow="Analytics"
        title="Incident Trends"
        meta={analytics?.last_event_timestamp ? formatTimestamp(analytics.last_event_timestamp) : "No trend data yet"}
      />

      <div className="runtime-grid runtime-grid--compact">
        <div className="runtime-item">
          <span>Trend Events</span>
          <strong>{analytics?.event_count ?? 0}</strong>
        </div>
        <div className="runtime-item">
          <span>Unique Tracks</span>
          <strong>{analytics?.unique_tracks ?? 0}</strong>
        </div>
        <div className="runtime-item">
          <span>Top Zones</span>
          <strong>{Object.keys(analytics?.zone_breakdown || {}).length}</strong>
        </div>
        <div className="runtime-item">
          <span>Severity Groups</span>
          <strong>{Object.keys(analytics?.severity_breakdown || {}).length}</strong>
        </div>
      </div>

      <div className="trend-chart">
        {hourlySeries.length === 0 ? (
          <p className="muted">No hourly trend data available yet.</p>
        ) : (
          hourlySeries.map((point) => {
            const height = Math.max(12, ((Number(point.count) || 0) / highest) * 100);
            return (
              <div key={point.label} className="trend-bar">
                <span className="trend-bar__column" style={{ height: `${height}%` }} />
                <span className="trend-bar__label">{point.label}</span>
                <strong>{point.count}</strong>
              </div>
            );
          })
        )}
      </div>

      <div className="small-grid">
        <section className="mini-panel">
          <h4>Top Tracks</h4>
          {topTracks.length === 0 ? (
            <p className="muted">No track ranking available.</p>
          ) : (
            topTracks.map(([trackId, count]) => (
              <div key={trackId} className="mini-row">
                <span>Track {trackId}</span>
                <strong>{count}</strong>
              </div>
            ))
          )}
        </section>

        <section className="mini-panel">
          <h4>Zone Breakdown</h4>
          <MetricList
            items={analytics?.zone_breakdown}
            emptyText="No restricted-zone entries logged yet."
          />
        </section>
      </div>
    </section>
  );
}

function AlertCard({ event, selected, onSelect }) {
  const alerts = event.alerts || [];
  const primaryAlert = alerts[0] || null;
  const allZones = alerts.flatMap((alert) => alert.violated_zones || []);

  return (
    <article
      className={`alert-card ${selected ? "alert-card--selected" : ""}`}
      onClick={() => onSelect(event.event_id)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          onSelect(event.event_id);
        }
      }}
    >
      <div className="alert-card__head">
        <div>
          <div className="alert-card__meta">
            <span>{formatTimestamp(event.timestamp_utc)}</span>
            <span>{formatRelative(event.timestamp_utc)}</span>
            <span>{event.site_name}</span>
          </div>
          <h4>{primaryAlert ? `${primaryAlert.class_name} incident` : "Threat incident"}</h4>
        </div>
        <div className="alert-card__head-right">
          <span className="inline-chip">Event {event.event_id}</span>
          <span className="inline-chip">Review required</span>
        </div>
      </div>

      <div className="alert-card__body">
        <section className="alert-section">
          <h5>Threat Details</h5>
          {alerts.map((alert, index) => {
            const severity = alert.severity || riskBand(alert.risk_score);
            const riskScore = Math.max(0, Math.min(100, Number(alert.risk_score) || 0));
            return (
              <div key={`${event.event_id}-${index}`} className="alert-entry">
                <div className="alert-entry__top">
                  <div>
                    <strong>{alert.class_name}</strong>
                    <span>
                      Track {alert.track_id ?? "N/A"} - {alert.track_age_frames ?? 1} frames
                    </span>
                  </div>
                  <span className={`severity-pill severity-pill--${severity}`}>{severity}</span>
                </div>
                <div className="meter meter--alert">
                  <span style={{ width: `${riskScore}%` }} />
                </div>
                <div className="alert-entry__meta">
                  <span>Risk {riskScore}</span>
                  <span>Speed {Number(alert.estimated_speed || 0).toFixed(1)} px/frame</span>
                </div>
              </div>
            );
          })}
        </section>

        <section className="alert-section">
          <h5>Zones</h5>
          {allZones.length > 0 ? (
            <div className="tag-wrap">
              {allZones.map((zone, index) => (
                <span key={`${zone}-${index}`} className="zone-tag">
                  {zone}
                </span>
              ))}
            </div>
          ) : (
            <p className="muted">No restricted-zone breach logged.</p>
          )}
        </section>

        <section className="alert-section">
          <h5>Evidence</h5>
          {event.evidence_url ? (
            <img className="evidence-image" src={event.evidence_url} alt={event.event_id} />
          ) : (
            <p className="muted">No evidence snapshot available.</p>
          )}
        </section>
      </div>
    </article>
  );
}

function IncidentDrawer({ event }) {
  const alerts = event?.alerts || [];
  const zones = alerts.flatMap((alert) => alert.violated_zones || []);

  if (!event) {
    return (
      <section className="panel panel--stack">
        <SectionHeader eyebrow="Selected incident" title="Incident Details" meta="Choose an incident" />
        <p className="muted">Click an alert card to inspect the full event record.</p>
      </section>
    );
  }

  return (
    <section className="panel panel--stack">
      <SectionHeader
        eyebrow="Selected incident"
        title="Incident Details"
        meta={`${formatTimestamp(event.timestamp_utc)} - ${event.event_id}`}
      />

      <div className="runtime-grid runtime-grid--compact">
        <div className="runtime-item">
          <span>Alert Count</span>
          <strong>{alerts.length}</strong>
        </div>
        <div className="runtime-item">
          <span>Zones Hit</span>
          <strong>{zones.length}</strong>
        </div>
        <div className="runtime-item">
          <span>Human Review</span>
          <strong>{event.human_review_required ? "Required" : "Not required"}</strong>
        </div>
        <div className="runtime-item">
          <span>Evidence</span>
          <strong>{event.evidence_frame ? "Captured" : "Missing"}</strong>
        </div>
      </div>

      {event.evidence_url ? (
        <img className="evidence-image evidence-image--large" src={event.evidence_url} alt={event.event_id} />
      ) : (
        <p className="muted">No evidence image available for this incident.</p>
      )}

      <div className="incident-stack">
        {alerts.map((alert, index) => (
          <div key={`${event.event_id}-detail-${index}`} className="incident-note">
            <div className="incident-note__top">
              <strong>{alert.class_name}</strong>
              <span className={`severity-pill severity-pill--${alert.severity || riskBand(alert.risk_score)}`}>
                {alert.severity || riskBand(alert.risk_score)}
              </span>
            </div>
            <div className="incident-note__meta">
              <span>Track {alert.track_id ?? "N/A"}</span>
              <span>Risk {alert.risk_score}</span>
              <span>Age {alert.track_age_frames ?? 1}</span>
              <span>Speed {Number(alert.estimated_speed || 0).toFixed(1)} px/frame</span>
            </div>
            {alert.violated_zones?.length > 0 ? (
              <div className="tag-wrap">
                {alert.violated_zones.map((zone) => (
                  <span key={`${event.event_id}-${zone}`} className="zone-tag">
                    {zone}
                  </span>
                ))}
              </div>
            ) : (
              <p className="muted">No zone breach registered for this detection.</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function DemoPanel({ scenarios, sample, onSampleChange, onRunDemo, running, result }) {
  return (
    <section className="panel panel--stack">
      <SectionHeader
        eyebrow="Simulation"
        title="Demo Scenario"
        meta="Replay a sample drone image for the presentation"
      />

      <div className="demo-controls">
        <select
          className="toolbar-select"
          value={sample}
          onChange={(event) => onSampleChange(event.target.value)}
        >
          {scenarios.length === 0 ? (
            <option value="">No sample inputs available</option>
          ) : (
            scenarios.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))
          )}
        </select>
        <button
          className="control-button"
          type="button"
          onClick={onRunDemo}
          disabled={running || scenarios.length === 0}
        >
          {running ? "Running demo..." : "Run Demo Scenario"}
        </button>
      </div>

      {result ? (
        <div className="demo-result">
          <div className="runtime-grid runtime-grid--compact">
            <div className="runtime-item">
              <span>Scenario</span>
              <strong>{result.sample_name}</strong>
            </div>
            <div className="runtime-item">
              <span>Threats Found</span>
              <strong>{result.threat_count}</strong>
            </div>
            <div className="runtime-item">
              <span>High Risk</span>
              <strong>{result.high_risk_count}</strong>
            </div>
            <div className="runtime-item">
              <span>Mode</span>
              <strong>{result.demo_mode ? "Simulation" : "Live"}</strong>
            </div>
          </div>
          <img className="evidence-image evidence-image--large" src={result.annotated_image_url} alt={result.sample_name} />
        </div>
      ) : (
        <p className="muted">
          Pick a bundled scenario and run it to show a ready-made demo without depending on the camera.
        </p>
      )}
    </section>
  );
}

function UploadPanel() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!selectedFile) {
      setError("Choose an image first.");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    setUploading(true);
    setError("");

    try {
      const response = await fetch("/analyze-image", {
        method: "POST",
        body: formData
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Image analysis failed.");
      }
      setResult(data);
    } catch (err) {
      setError(err.message || "Image analysis failed.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <section className="panel upload-panel">
      <SectionHeader
        eyebrow="Validation"
        title="Quick Image Test"
        meta="Run a one-off scan without starting the live stream"
      />
      <form className="upload-form" onSubmit={handleSubmit}>
        <label className="upload-input">
          <span className="upload-input__label">Choose image</span>
          <input
            type="file"
            accept=".jpg,.jpeg,.png,.bmp,.webp"
            onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button className="upload-button" type="submit" disabled={uploading}>
          {uploading ? "Analyzing..." : "Analyze Image"}
        </button>
      </form>
      <div className="upload-status">
        <span className="inline-chip">File {selectedFile ? selectedFile.name : "none selected"}</span>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
      {result ? (
        <div className="upload-result">
          <div className="runtime-grid runtime-grid--compact">
            <div className="runtime-item">
              <span>Threats Found</span>
              <strong>{result.threat_count}</strong>
            </div>
            <div className="runtime-item">
              <span>High Risk</span>
              <strong>{result.high_risk_count}</strong>
            </div>
          </div>
          <img
            className="evidence-image evidence-image--large"
            src={result.annotated_image_url}
            alt="Analyzed upload"
          />
          <div className="upload-findings">
            {result.detections.length === 0 ? (
              <p className="muted">No watched classes were detected in this image.</p>
            ) : (
              result.detections.map((detection, index) => {
                const severity = detection.severity || riskBand(detection.risk_score);
                return (
                  <div key={`${detection.track_id ?? "upload"}-${index}`} className="upload-finding">
                    <div>
                      <strong>{detection.class_name}</strong>
                      <span>
                        Track {detection.track_id ?? "N/A"} - {detection.track_age_frames ?? 1} frames
                      </span>
                    </div>
                    <div className="upload-finding__right">
                      <span className={`severity-pill severity-pill--${severity}`}>{severity}</span>
                      <strong>Risk {detection.risk_score}</strong>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      ) : (
        <p className="muted">
          Upload a photo here to test the pipeline without starting the live detector.
        </p>
      )}
    </section>
  );
}

export default function App() {
  const [summary, setSummary] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [config, setConfig] = useState(null);
  const [detectorStatus, setDetectorStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [demoScenarios, setDemoScenarios] = useState([]);
  const [demoSample, setDemoSample] = useState("");
  const [demoResult, setDemoResult] = useState(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [error, setError] = useState("");
  const [detectorBusy, setDetectorBusy] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [selectedEventId, setSelectedEventId] = useState(getInitialSelectedEventId);
  const [activePage, setActivePage] = useState(getInitialPage);
  const [presentationMode, setPresentationMode] = useState(getInitialPresentationMode);
  const [viewportHint] = useState(getViewportHint);

  useEffect(() => {
    let active = true;

    const load = async () => {
      const [summaryData, alertsData, configData, detectorData, analyticsData, demoData] = await Promise.allSettled([
        fetchJson("/summary"),
        fetchJson("/alerts?limit=24"),
        fetchJson("/config"),
        fetchJson("/detector/status"),
        fetchJson("/analytics"),
        fetchJson("/demo/scenarios")
      ]);

      if (!active) {
        return;
      }

      const failures = [];

      if (summaryData.status === "fulfilled") {
        setSummary(summaryData.value);
        setRuntime(summaryData.value.runtime || null);
      } else {
        failures.push("summary");
      }

      if (alertsData.status === "fulfilled") {
        setAlerts(alertsData.value);
      } else {
        failures.push("alerts");
      }

      if (configData.status === "fulfilled") {
        setConfig(configData.value);
      } else {
        failures.push("config");
      }

      if (detectorData.status === "fulfilled") {
        setDetectorStatus(detectorData.value);
      } else {
        failures.push("detector");
      }

      if (analyticsData.status === "fulfilled") {
        setAnalytics(analyticsData.value);
      } else {
        failures.push("analytics");
      }

      if (demoData.status === "fulfilled") {
        const samples = demoData.value.samples || [];
        setDemoScenarios(samples);
        setDemoSample((current) => current || demoData.value.default_sample || samples[0] || "");
      } else {
        failures.push("demo");
      }

      setLastSyncedAt(new Date());
      setError(failures.length > 0 ? `Some dashboard data could not load: ${failures.join(", ")}.` : "");
    };

    load();
    const intervalId = window.setInterval(load, refreshMs);

    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, []);

  useEffect(() => {
    if (!selectedEventId && alerts.length > 0) {
      setSelectedEventId(alerts[0].event_id);
    }
    if (selectedEventId && !alerts.some((event) => event.event_id === selectedEventId) && alerts.length > 0) {
      setSelectedEventId(alerts[0].event_id);
    }
  }, [alerts, selectedEventId]);

  useEffect(() => {
    const scrollToHint = () => {
      if (viewportHint.scroll > 0) {
        window.scrollTo(0, viewportHint.scroll);
      }

      if (viewportHint.focus === "evidence") {
        const target = document.querySelector(".evidence-image--large");
        target?.scrollIntoView({ block: "center" });
      }
    };

    const timer = window.setTimeout(scrollToHint, 900);
    return () => window.clearTimeout(timer);
  }, [activePage, viewportHint.focus, viewportHint.scroll]);

  const controlDetector = async (action) => {
    setDetectorBusy(true);
    try {
      const response = await fetch(`/detector/${action}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `Detector ${action} failed.`);
      }
      setRuntime(data.runtime || data);
      setDetectorStatus(data);
      setError("");
    } catch (err) {
      setError(err.message || `Detector ${action} failed.`);
    } finally {
      setDetectorBusy(false);
    }
  };

  const handleExportReport = async () => {
    try {
      const response = await fetch("/report");
      if (!response.ok) {
        throw new Error("Report export failed.");
      }
      const text = await response.text();
      const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `drone-threat-report-${new Date().toISOString().slice(0, 10)}.txt`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setError("");
    } catch (err) {
      setError(err.message || "Report export failed.");
    }
  };

  const handleRunDemo = async () => {
    if (!demoSample) {
      setError("No demo sample is available.");
      return;
    }

    setDemoBusy(true);
    try {
      const response = await fetch(`/demo/run?sample=${encodeURIComponent(demoSample)}`, {
        method: "POST"
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Demo scenario failed.");
      }
      setDemoResult(data);
      setError("");
    } catch (err) {
      setError(err.message || "Demo scenario failed.");
    } finally {
      setDemoBusy(false);
    }
  };

  const filteredAlerts = useMemo(() => {
    const search = searchTerm.trim().toLowerCase();
    return alerts.filter((event) => {
      const alertList = event.alerts || [];
      const eventText = [
        event.event_id,
        event.site_name,
        event.timestamp_utc,
        ...alertList.map((alert) => alert.class_name),
        ...alertList.flatMap((alert) => alert.violated_zones || [])
      ]
        .join(" ")
        .toLowerCase();

      const severityMatch =
        severityFilter === "all" ||
        alertList.some((alert) => (alert.severity || riskBand(alert.risk_score)) === severityFilter);

      return (!search || eventText.includes(search)) && severityMatch;
    });
  }, [alerts, searchTerm, severityFilter]);

  const selectedEvent = useMemo(() => {
    return filteredAlerts.find((event) => event.event_id === selectedEventId) || filteredAlerts[0] || null;
  }, [filteredAlerts, selectedEventId]);

  const severityOptions = useMemo(() => {
    const values = new Set(["all"]);
    Object.keys(analytics?.severity_breakdown || {}).forEach((key) => values.add(key));
    alerts.forEach((event) => {
      (event.alerts || []).forEach((alert) => values.add(alert.severity || riskBand(alert.risk_score)));
    });
    return Array.from(values);
  }, [analytics, alerts]);

  const latestEvent = summary?.latest_event || alerts[0] || null;
  const incidentsLast = summary?.total_events ?? 0;
  const postureLabel = runtime?.running
    ? "Active monitoring"
    : incidentsLast > 0
      ? "Evidence review mode"
      : "Standby";
  const pageTabs = [
    { id: "overview", label: "Overview" },
    { id: "live", label: "Live Feed" },
    { id: "incidents", label: "Incidents" },
    { id: "analytics", label: "Analytics" },
    { id: "demo", label: "Demo Lab" }
  ];
  const visibleTabs = presentationMode
    ? pageTabs.filter((tab) => ["overview", "live", "demo"].includes(tab.id))
    : pageTabs;

  return (
    <main className={`app-shell ${presentationMode ? "app-shell--presentation" : ""}`}>
      <section className="hero">
        <div className="hero-copy-block">
          <p className="eyebrow">Airport Security Monitoring</p>
          <h1>Drone Threat Command Dashboard</h1>
          <p className="hero-copy">
            Live incident review for restricted airspace, combining detection, tracking,
            geofencing, and evidence logging in one operator view.
          </p>

          <div className="chip-row chip-row--wrap">
            <span className="inline-chip">{postureLabel}</span>
            <span className="inline-chip">
              Refresh every {Math.round(refreshMs / 1000)} seconds
            </span>
            <span className="inline-chip">
              Last sync {lastSyncedAt ? lastSyncedAt.toLocaleTimeString() : fallbackText}
            </span>
          </div>
        </div>

        <div className="hero-panel">
          <div className="hero-panel__topline">
            <div>
              <span className="hero-panel__label">Protected Site</span>
              <strong>{config?.site_name ?? "Loading..."}</strong>
            </div>
            <button
              className="presentation-toggle"
              type="button"
              onClick={() => setPresentationMode((current) => !current)}
              aria-pressed={presentationMode}
            >
              {presentationMode ? "Presentation mode on" : "Presentation mode off"}
            </button>
          </div>

          <div className="hero-panel__stack">
            <div className="hero-panel__block">
              <span className="hero-panel__label">Mode</span>
              <p>{presentationMode ? "Simplified demo view" : "Full operator view"}</p>
            </div>
            {!presentationMode ? (
              <>
                <div className="hero-panel__block">
                  <span className="hero-panel__label">Sensors</span>
                  <p>
                    Camera {config?.sensor_stack?.camera_enabled ? "online" : "offline"} | Radar{" "}
                    {config?.sensor_stack?.radar_enabled ? "online" : "offline"} | RF{" "}
                    {config?.sensor_stack?.rf_sensor_enabled ? "online" : "offline"}
                  </p>
                </div>
                <div className="hero-panel__block">
                  <span className="hero-panel__label">Zones</span>
                  <p>{config?.restricted_zones?.length ?? 0} monitored geofences</p>
                </div>
                <div className="hero-panel__block">
                  <span className="hero-panel__label">Watchlist</span>
                  <p>{config?.suspicious_classes?.join(", ") ?? "Loading..."}</p>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </section>

      <nav className="page-nav" aria-label="Dashboard views">
        {visibleTabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={`page-nav__item ${activePage === tab.id ? "page-nav__item--active" : ""}`}
            onClick={() => setActivePage(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {error ? <div className="error-banner">{error}</div> : null}

      {activePage === "overview" ? (
        <section className="page-stack">
          {!presentationMode ? (
            <section className="stats-grid">
              <StatCard
                label="Total Events"
                value={summary?.total_events ?? 0}
                tone="neutral"
                detail="Logged alert records"
              />
              <StatCard
                label="Tracked Threats"
                value={summary?.tracked_threats ?? 0}
                tone="cool"
                detail="Unique object tracks"
              />
              <StatCard
                label="Critical Alerts"
                value={summary?.critical_alerts ?? 0}
                tone="danger"
                detail="Highest-priority events"
              />
              <StatCard
                label="High Alerts"
                value={summary?.high_alerts ?? 0}
                tone="warning"
                detail="Escalation-worthy events"
              />
            </section>
          ) : null}

          <section className="content-grid content-grid--overview">
            <SummaryPanel
              config={config}
              summary={summary}
              runtime={runtime}
              detectorStatus={detectorStatus}
            />
            <section className="panel panel--stack">
              <SectionHeader
                eyebrow="Latest incident"
                title="Quick Review"
                meta={latestEvent ? formatTimestamp(latestEvent.timestamp_utc) : "No incident selected"}
              />
              {latestEvent ? (
                <article className="latest-incident">
                  <div className="latest-incident__meta">
                    <span className="inline-chip">{latestEvent.site_name}</span>
                    <span className="inline-chip">{latestEvent.event_id}</span>
                    <span className="inline-chip">{formatRelative(latestEvent.timestamp_utc)}</span>
                  </div>
                  <div className="latest-incident__grid">
                    <div className="runtime-item">
                      <span>Alerts in event</span>
                      <strong>{latestEvent.alerts?.length ?? 0}</strong>
                    </div>
                    <div className="runtime-item">
                      <span>Human review</span>
                      <strong>{latestEvent.human_review_required ? "Required" : "Not required"}</strong>
                    </div>
                    <div className="runtime-item">
                      <span>Evidence</span>
                      <strong>{latestEvent.evidence_frame ? "Captured" : "Missing"}</strong>
                    </div>
                    <div className="runtime-item">
                      <span>Zones</span>
                      <strong>
                        {(latestEvent.alerts || []).flatMap((alert) => alert.violated_zones || []).length}
                      </strong>
                    </div>
                  </div>
                  {latestEvent.evidence_url ? (
                    <img
                      className="evidence-image evidence-image--large"
                      src={latestEvent.evidence_url}
                      alt={latestEvent.event_id}
                    />
                  ) : (
                    <p className="muted">No evidence image available for the latest event.</p>
                  )}
                </article>
              ) : (
                <p className="muted">No recent incident to display yet.</p>
              )}
            </section>
          </section>
        </section>
      ) : null}

      {activePage === "live" ? (
        <section className="page-stack">
          <RuntimePanel
            runtime={runtime}
            detectorStatus={detectorStatus}
            onStartCamera={() => controlDetector("start")}
            onStopCamera={() => controlDetector("stop")}
            busy={detectorBusy}
          />
          {!presentationMode ? (
            <section className="panel panel--stack">
              <SectionHeader
                eyebrow="Command"
                title="Status Notes"
                meta="Operator-only detail"
              />
              <div className="runtime-grid runtime-grid--compact">
                <div className="runtime-item">
                  <span>Active Tracks</span>
                  <strong>{runtime?.active_tracks ?? 0}</strong>
                </div>
                <div className="runtime-item">
                  <span>Live Alerts</span>
                  <strong>{runtime?.active_alerts ?? 0}</strong>
                </div>
                <div className="runtime-item">
                  <span>Managed By API</span>
                  <strong>{detectorStatus?.managed_by_api ? "Yes" : "No"}</strong>
                </div>
                <div className="runtime-item">
                  <span>PID</span>
                  <strong>{detectorStatus?.pid ?? "n/a"}</strong>
                </div>
              </div>
            </section>
          ) : null}
          <section className="panel panel--stack">
            <SectionHeader
              eyebrow="Live feed"
              title="Current Frame"
              meta={runtime?.latest_frame_url ? "Annotated detector output" : "Waiting for detector output"}
            />
            {runtime?.latest_frame_url ? (
              <img
                className="evidence-image evidence-image--large"
                src={`${runtime.latest_frame_url}?v=${runtime?.last_updated_epoch ?? Date.now()}`}
                alt="Current detector frame"
              />
            ) : (
              <div className="live-preview live-preview--tall">
                <strong>No live frame yet</strong>
                <span>Start the detector to surface its latest annotated frame here.</span>
              </div>
            )}
          </section>
        </section>
      ) : null}

      {activePage === "incidents" ? (
        <section className="page-stack">
          <section className="panel panel--stack">
            <SectionHeader
              eyebrow="Incident history"
              title="Recent Incidents"
              meta={`${filteredAlerts.length} records shown`}
              action={
                presentationMode ? null : (
                  <div className="toolbar-actions">
                    <input
                      className="toolbar-search"
                      type="search"
                      placeholder="Search event, zone, or class"
                      value={searchTerm}
                      onChange={(event) => setSearchTerm(event.target.value)}
                    />
                    <select
                      className="toolbar-select"
                      value={severityFilter}
                      onChange={(event) => setSeverityFilter(event.target.value)}
                    >
                      {severityOptions.map((option) => (
                        <option key={option} value={option}>
                          {option === "all" ? "All severities" : option}
                        </option>
                      ))}
                    </select>
                    <button
                      className="control-button control-button--secondary"
                      type="button"
                      onClick={handleExportReport}
                    >
                      Export Report
                    </button>
                  </div>
                )
              }
            />
            {!presentationMode ? (
              <div className="toolbar-note">
                <span className="inline-chip">Filter and click any card to inspect it in the drawer.</span>
              </div>
            ) : null}
            <div className="alerts-stack">
              {filteredAlerts.length === 0 ? (
                <p className="muted">No alerts match the current filters.</p>
              ) : (
                filteredAlerts.map((event) => (
                  <AlertCard
                    key={event.event_id}
                    event={event}
                    selected={event.event_id === selectedEventId}
                    onSelect={setSelectedEventId}
                  />
                ))
              )}
            </div>
          </section>
          {!presentationMode ? <IncidentDrawer event={selectedEvent} /> : null}
        </section>
      ) : null}

      {activePage === "analytics" ? (
        <section className="page-stack">
          <AnalyticsPanel analytics={analytics} />
          {!presentationMode ? (
            <section className="panel panel--stack">
              <SectionHeader
                eyebrow="Command"
                title="Operational Snapshot"
                meta={`${config?.site_name ?? "Loading..."} - ${summary?.total_events ?? 0} events`}
              />
              <div className="runtime-grid runtime-grid--compact">
                <div className="runtime-item">
                  <span>Watched Classes</span>
                  <strong>{config?.suspicious_classes?.length ?? 0}</strong>
                </div>
                <div className="runtime-item">
                  <span>Restricted Zones</span>
                  <strong>{config?.restricted_zones?.length ?? 0}</strong>
                </div>
                <div className="runtime-item">
                  <span>Critical Alerts</span>
                  <strong>{summary?.critical_alerts ?? 0}</strong>
                </div>
                <div className="runtime-item">
                  <span>High Alerts</span>
                  <strong>{summary?.high_alerts ?? 0}</strong>
                </div>
              </div>
              <MetricList
                items={analytics?.severity_breakdown}
                emptyText="No severity data available yet."
              />
            </section>
          ) : null}
        </section>
      ) : null}

      {activePage === "demo" ? (
        <section className="page-stack">
          <DemoPanel
            scenarios={demoScenarios}
            sample={demoSample}
            onSampleChange={setDemoSample}
            onRunDemo={handleRunDemo}
            running={demoBusy}
            result={demoResult}
          />
          {!presentationMode ? <UploadPanel /> : null}
        </section>
      ) : null}
    </main>
  );
}
