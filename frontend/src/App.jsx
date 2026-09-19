import { useEffect, useMemo, useRef, useState } from "react";

const refreshMs = 4000;
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
  if (!value || typeof value !== "string") return null;
  const match = value.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if (!match) return null;
  const [, year, month, day, hour, minute, second] = match;
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second));
}

function formatTimestamp(value) {
  const parsed = parseCompactUtc(value);
  if (!parsed) return value ?? fallbackText;
  return timestampFormatter.format(parsed);
}

function formatRelative(value) {
  const parsed = parseCompactUtc(value);
  if (!parsed) return fallbackText;
  const deltaSeconds = Math.round((parsed.getTime() - Date.now()) / 1000);
  const absSeconds = Math.abs(deltaSeconds);
  if (absSeconds < 60) return relativeFormatter.format(deltaSeconds, "second");
  if (absSeconds < 3600) return relativeFormatter.format(Math.round(deltaSeconds / 60), "minute");
  if (absSeconds < 86400) return relativeFormatter.format(Math.round(deltaSeconds / 3600), "hour");
  return relativeFormatter.format(Math.round(deltaSeconds / 86400), "day");
}

function riskBand(score) {
  const value = Math.max(0, Math.min(100, Number(score) || 0));
  if (value >= 85) return "critical";
  if (value >= 70) return "high";
  if (value >= 50) return "medium";
  return "low";
}

// --- Tactical Web Audio Alarm Generator ---
function playTacticalBeep(audioCtx, type = "warning") {
  if (!audioCtx) return;
  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain);
    gain.connect(audioCtx.destination);

    if (type === "critical") {
      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.35);
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
      osc.start(audioCtx.currentTime);
      osc.stop(audioCtx.currentTime + 0.35);
    } else {
      osc.type = "sine";
      osc.frequency.setValueAtTime(600, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);
      osc.start(audioCtx.currentTime);
      osc.stop(audioCtx.currentTime + 0.2);
    }
  } catch (e) {
    console.error("Audio synth error", e);
  }
}

// --- Tactical Radar Scope Component ---
function RadarScope({ radarTracks = [] }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let angle = 0;
    let animationId;

    const render = () => {
      const w = canvas.width;
      const h = canvas.height;
      const cx = w / 2;
      const cy = h / 2;
      const maxR = Math.min(cx, cy) - 20;

      // Dark background
      ctx.fillStyle = "#07111e";
      ctx.fillRect(0, 0, w, h);

      // Range Rings
      ctx.strokeStyle = "rgba(116, 216, 208, 0.25)";
      ctx.lineWidth = 1;
      [0.25, 0.5, 0.75, 1.0].forEach((ratio) => {
        ctx.beginPath();
        ctx.arc(cx, cy, maxR * ratio, 0, Math.PI * 2);
        ctx.stroke();

        ctx.fillStyle = "rgba(116, 216, 208, 0.5)";
        ctx.font = "10px monospace";
        ctx.fillText(`${Math.round(1500 * ratio)}m`, cx + 6, cy - maxR * ratio + 12);
      });

      // Crosshairs & Degree lines
      ctx.beginPath();
      ctx.moveTo(cx, cy - maxR);
      ctx.lineTo(cx, cy + maxR);
      ctx.moveTo(cx - maxR, cy);
      ctx.lineTo(cx + maxR, cy);
      ctx.stroke();

      // Sweeping Beam
      const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, maxR);
      grad.addColorStop(0, "rgba(116, 216, 208, 0.4)");
      grad.addColorStop(1, "rgba(116, 216, 208, 0.0)");

      ctx.save();
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, maxR, angle, angle + 0.35);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.restore();

      // Target Blips
      radarTracks.forEach((track) => {
        const rad = ((track.azimuth_deg - 90) * Math.PI) / 180;
        const distRatio = Math.min(1.0, track.range_meters / 1500);
        const bx = cx + Math.cos(rad) * (maxR * distRatio);
        const by = cy + Math.sin(rad) * (maxR * distRatio);

        ctx.beginPath();
        ctx.arc(bx, by, 6, 0, Math.PI * 2);
        ctx.fillStyle = track.threat_level === "critical" ? "#ff6a67" : "#ffb74d";
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.stroke();

        ctx.fillStyle = "#fff";
        ctx.font = "11px sans-serif";
        ctx.fillText(`T-${track.track_id} (${track.range_meters}m)`, bx + 9, by - 6);
      });

      angle = (angle + 0.03) % (Math.PI * 2);
      animationId = requestAnimationFrame(render);
    };

    render();
    return () => cancelAnimationFrame(animationId);
  }, [radarTracks]);

  return (
    <div className="radar-container">
      <div className="radar-header">
        <h4>Pulse-Doppler 3D Radar Scope</h4>
        <span className="inline-chip">Azimuth 360° | Max Range 1500m</span>
      </div>
      <canvas ref={canvasRef} width={380} height={380} className="radar-canvas" />
    </div>
  );
}

// --- RF Spectrum Widget ---
function RFSpectrumWidget({ rfSignals = [] }) {
  return (
    <div className="rf-widget">
      <div className="rf-header">
        <h4>RF Telemetry & Spectrum Analyzer</h4>
        <span className="inline-chip">2.4 GHz / 5.8 GHz Bands</span>
      </div>
      <div className="rf-signals-list">
        {rfSignals.length === 0 ? (
          <p className="muted">No RF communication signatures detected in active sector.</p>
        ) : (
          rfSignals.map((sig, idx) => (
            <div key={idx} className="rf-card">
              <div className="rf-card__top">
                <strong>{sig.protocol}</strong>
                <span className="rf-freq">{sig.frequency_mhz} MHz</span>
              </div>
              <div className="rf-meter">
                <div className="rf-meter__fill" style={{ width: `${Math.min(100, Math.max(10, 100 + sig.rssi_dbm))}%` }} />
              </div>
              <div className="rf-card__bottom">
                <span>Signal RSSI: {sig.rssi_dbm} dBm</span>
                <span>SNR: {sig.signal_snr_db} dB</span>
                {sig.remote_id_broadcast && <span className="badge-remote-id">Remote ID Broadcast</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// --- C-UAS Countermeasures Component ---
function CountermeasureStation({ onTrigger, activeActions = [], busy = false }) {
  return (
    <section className="panel panel--stack">
      <SectionHeader
        eyebrow="Active Defense (C-UAS)"
        title="Electronic Countermeasures Station"
        meta="Authorized Personnel Only"
      />
      <p className="muted">
        Engage non-destructive mitigation protocols to neutralize unauthorized drone incursions into restricted airspace.
      </p>

      <div className="countermeasure-grid">
        <button
          className="cuas-btn cuas-btn--jam"
          type="button"
          disabled={busy}
          onClick={() => onTrigger("RF_JAMMING_DIRECTIONAL")}
        >
          <div className="cuas-btn__icon">📡</div>
          <div>
            <strong>Directional RF Jammer</strong>
            <span>Disrupt 2.4/5.8GHz Link (Force RTH/Descent)</span>
          </div>
        </button>

        <button
          className="cuas-btn cuas-btn--gnss"
          type="button"
          disabled={busy}
          onClick={() => onTrigger("GNSS_SPOOFING_DEFENSE")}
        >
          <div className="cuas-btn__icon">🛰️</div>
          <div>
            <strong>GNSS Geo-Defend Override</strong>
            <span>Inject Virtual No-Fly Boundary</span>
          </div>
        </button>

        <button
          className="cuas-btn cuas-btn--siren"
          type="button"
          disabled={busy}
          onClick={() => onTrigger("ACOUSTIC_SIREN")}
        >
          <div className="cuas-btn__icon">🔊</div>
          <div>
            <strong>Acoustic Deterrent Siren</strong>
            <span>High-Decibel Directional Warning</span>
          </div>
        </button>

        <button
          className="cuas-btn cuas-btn--atc"
          type="button"
          disabled={busy}
          onClick={() => onTrigger("ATC_NOTIFY")}
        >
          <div className="cuas-btn__icon">🛫</div>
          <div>
            <strong>Notify Air Traffic Control</strong>
            <span>Broadcast Priority Alert to Tower</span>
          </div>
        </button>
      </div>

      <div className="cuas-log-panel">
        <h4>Active & Recent Engagements</h4>
        {activeActions.length === 0 ? (
          <p className="muted">No countermeasures deployed during this operational shift.</p>
        ) : (
          activeActions.map((act, i) => (
            <div key={i} className="cuas-log-item">
              <span className="cuas-status-badge">ENGAGED</span>
              <strong>{act.action_type}</strong>
              <span>Target: {act.target_track_id ? `Track ${act.target_track_id}` : "Sector Wide"}</span>
              <span>Efficacy: {act.estimated_efficacy}%</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

// --- Live Video Player Component ---
function EmbeddedLivePlayer({ streaming, onToggleStream }) {
  return (
    <div className="video-player-card">
      <div className="video-player-header">
        <div className="flex-center gap-8">
          <span className={`live-dot ${streaming ? "live-dot--on" : "live-dot--off"}`} />
          <strong>AI Optical Surveillance Feed</strong>
        </div>
        <div className="flex-center gap-8">
          <button className="control-button control-button--secondary" type="button" onClick={onToggleStream}>
            {streaming ? "Pause Stream" : "Resume Stream"}
          </button>
        </div>
      </div>
      <div className="video-viewport">
        {streaming ? (
          <img className="video-stream-img" src="/video_feed" alt="Real-time Drone Surveillance Stream" />
        ) : (
          <div className="video-paused-placeholder">
            <strong>Stream Paused</strong>
            <span>Click Resume Stream to restart the live MJPEG feed.</span>
          </div>
        )}
      </div>
    </div>
  );
}

// --- UI Stat Card ---
function StatCard({ label, value, tone, detail }) {
  return (
    <div className={`stat-card stat-card--${tone}`}>
      <span className="stat-card__label">{label}</span>
      <strong className="stat-card__value">{value}</strong>
      {detail ? <span className="stat-card__detail">{detail}</span> : null}
    </div>
  );
}

// --- Section Header ---
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

// --- Main App Component ---
export default function App() {
  const [summary, setSummary] = useState(null);
  const [runtime, setRuntime] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [config, setConfig] = useState(null);
  const [detectorStatus, setDetectorStatus] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [sensorTelemetry, setSensorTelemetry] = useState(null);
  const [countermeasures, setCountermeasures] = useState([]);
  const [demoScenarios, setDemoScenarios] = useState([]);
  const [demoSample, setDemoSample] = useState("");
  const [demoResult, setDemoResult] = useState(null);
  const [demoBusy, setDemoBusy] = useState(false);
  const [error, setError] = useState("");
  const [detectorBusy, setDetectorBusy] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [selectedEventId, setSelectedEventId] = useState("");
  const [activePage, setActivePage] = useState("overview");
  const [presentationMode, setPresentationMode] = useState(false);
  const [isStreaming, setIsStreaming] = useState(true);
  const [audioAlarmEnabled, setAudioAlarmEnabled] = useState(false);
  const audioCtxRef = useRef(null);

  // Initialize Audio Context on user interaction
  const toggleAudioAlarm = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    setAudioAlarmEnabled((prev) => !prev);
  };

  useEffect(() => {
    let active = true;

    const load = async () => {
      const [
        summaryData,
        alertsData,
        configData,
        detectorData,
        analyticsData,
        demoData,
        sensorsData,
        cuasData
      ] = await Promise.allSettled([
        fetchJson("/summary"),
        fetchJson("/alerts?limit=24"),
        fetchJson("/config"),
        fetchJson("/detector/status"),
        fetchJson("/analytics"),
        fetchJson("/demo/scenarios"),
        fetchJson("/sensors/telemetry"),
        fetchJson("/countermeasures/status")
      ]);

      if (!active) return;

      if (summaryData.status === "fulfilled") {
        setSummary(summaryData.value);
        setRuntime(summaryData.value.runtime || null);
      }
      if (alertsData.status === "fulfilled") setAlerts(alertsData.value);
      if (configData.status === "fulfilled") setConfig(configData.value);
      if (detectorData.status === "fulfilled") setDetectorStatus(detectorData.value);
      if (analyticsData.status === "fulfilled") setAnalytics(analyticsData.value);
      if (sensorsData.status === "fulfilled") setSensorTelemetry(sensorsData.value);
      if (cuasData.status === "fulfilled") setCountermeasures(cuasData.value.active_engagements || []);
      if (demoData.status === "fulfilled") {
        const samples = demoData.value.samples || [];
        setDemoScenarios(samples);
        setDemoSample((current) => current || demoData.value.default_sample || samples[0] || "");
      }

      setLastSyncedAt(new Date());

      // Trigger tactical audio if critical threat exists and audio enabled
      if (audioAlarmEnabled && audioCtxRef.current) {
        const hasCritical = alertsData.status === "fulfilled" && alertsData.value.some((ev) =>
          (ev.alerts || []).some((a) => a.severity === "critical")
        );
        if (hasCritical) {
          playTacticalBeep(audioCtxRef.current, "critical");
        }
      }
    };

    load();
    const intervalId = window.setInterval(load, refreshMs);
    return () => {
      active = false;
      window.clearInterval(intervalId);
    };
  }, [audioAlarmEnabled]);

  const controlDetector = async (action) => {
    setDetectorBusy(true);
    try {
      const response = await fetch(`/detector/${action}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Detector ${action} failed.`);
      setRuntime(data.runtime || data);
      setDetectorStatus(data);
      setError("");
    } catch (err) {
      setError(err.message || `Detector ${action} failed.`);
    } finally {
      setDetectorBusy(false);
    }
  };

  const handleTriggerCountermeasure = async (action) => {
    try {
      const response = await fetch(`/countermeasures/trigger?action=${encodeURIComponent(action)}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Countermeasure failed.");
      setCountermeasures((prev) => [data.engagement, ...prev]);
    } catch (err) {
      setError(err.message || "Countermeasure execution failed.");
    }
  };

  const handleExport = (format) => {
    window.open(`/report/${format === "text" ? "" : format}`, "_blank");
  };

  const handleRunDemo = async () => {
    if (!demoSample) return;
    setDemoBusy(true);
    try {
      const response = await fetch(`/demo/run?sample=${encodeURIComponent(demoSample)}`, { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Demo scenario failed.");
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

  const pageTabs = [
    { id: "overview", label: "Overview" },
    { id: "live", label: "Live Optical Feed" },
    { id: "radar", label: "Radar & RF Scope" },
    { id: "countermeasures", label: "C-UAS Defense" },
    { id: "incidents", label: "Incidents" },
    { id: "analytics", label: "Analytics" },
    { id: "demo", label: "Demo Lab" }
  ];

  return (
    <main className={`app-shell ${presentationMode ? "app-shell--presentation" : ""}`}>
      {/* Hero Section */}
      <section className="hero">
        <div className="hero-copy-block">
          <p className="eyebrow">Enterprise Airspace Defense</p>
          <h1>Drone Threat Command Dashboard</h1>
          <p className="hero-copy">
            Unified multi-sensor threat intelligence combining YOLOv8 computer vision, Pulse-Doppler radar tracking, RF spectrum telemetry, and active electronic countermeasures.
          </p>

          <div className="chip-row chip-row--wrap">
            <span className="inline-chip">{runtime?.running ? "🟢 Active Surveillance" : "🟡 Standby Review"}</span>
            <span className="inline-chip">Sync: {lastSyncedAt ? lastSyncedAt.toLocaleTimeString() : fallbackText}</span>
            <button
              className={`alarm-toggle-btn ${audioAlarmEnabled ? "alarm-toggle-btn--on" : ""}`}
              onClick={toggleAudioAlarm}
              title="Toggle Web Audio Tactical Siren"
            >
              {audioAlarmEnabled ? "🔊 Audio Alarm ON" : "🔇 Audio Alarm Muted"}
            </button>
          </div>
        </div>

        <div className="hero-panel">
          <div className="hero-panel__topline">
            <div>
              <span className="hero-panel__label">Protected Facility</span>
              <strong>{config?.site_name ?? "Loading..."}</strong>
            </div>
            <button
              className="presentation-toggle"
              type="button"
              onClick={() => setPresentationMode((curr) => !curr)}
            >
              {presentationMode ? "Full Operator View" : "Presentation View"}
            </button>
          </div>

          <div className="hero-panel__stack">
            <div className="hero-panel__block">
              <span className="hero-panel__label">Sensor Fusion Status</span>
              <div className="chip-row chip-row--wrap" style={{ marginTop: 6 }}>
                <SensorPill label="Optical" enabled={!!config?.sensor_stack?.camera_enabled} />
                <SensorPill label="Radar" enabled={!!config?.sensor_stack?.radar_enabled} />
                <SensorPill label="RF Scanner" enabled={!!config?.sensor_stack?.rf_sensor_enabled} />
                <SensorPill label="Acoustic" enabled={true} />
              </div>
            </div>
            <div className="hero-panel__block">
              <span className="hero-panel__label">Quick Export</span>
              <div className="export-bar">
                <button className="export-btn" onClick={() => handleExport("csv")}>Download CSV</button>
                <button className="export-btn" onClick={() => handleExport("json")}>Export JSON</button>
                <button className="export-btn" onClick={() => handleExport("text")}>Summary TXT</button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Navigation */}
      <nav className="page-nav" aria-label="Dashboard views">
        {pageTabs.map((tab) => (
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

      {/* OVERVIEW TAB */}
      {activePage === "overview" && (
        <section className="page-stack">
          <section className="stats-grid">
            <StatCard label="Total Alert Events" value={summary?.total_events ?? 0} tone="neutral" detail="Logged incidents" />
            <StatCard label="Tracked Targets" value={summary?.tracked_threats ?? 0} tone="cool" detail="Unique UAV tracks" />
            <StatCard label="Critical Incursions" value={summary?.critical_alerts ?? 0} tone="danger" detail="Restricted zone breaches" />
            <StatCard label="Active Sensors" value="4 Online" tone="warning" detail="Optical / Radar / RF / Audio" />
          </section>

          <div className="content-grid content-grid--overview">
            <section className="panel panel--stack">
              <SectionHeader eyebrow="Live Airspace" title="Real-Time Detection Feed" meta="MJPEG Stream" />
              <EmbeddedLivePlayer streaming={isStreaming} onToggleStream={() => setIsStreaming(!isStreaming)} />
            </section>
            <section className="panel panel--stack">
              <SectionHeader eyebrow="Multi-Sensor" title="Airspace Radar Scope" meta="Real-time Polar Tracking" />
              <RadarScope radarTracks={sensorTelemetry?.radar_tracks || []} />
            </section>
          </div>
        </section>
      )}

      {/* LIVE OPTICAL FEED TAB */}
      {activePage === "live" && (
        <section className="page-stack">
          <div className="panel panel--stack">
            <SectionHeader eyebrow="High-Resolution Optical Stream" title="Camera Surveillance Feed" meta="YOLOv8 Real-Time Inference" />
            <div className="control-row" style={{ marginBottom: 12 }}>
              <button className="control-button" type="button" onClick={() => controlDetector("start")} disabled={detectorBusy}>
                Start Native Camera
              </button>
              <button className="control-button control-button--secondary" type="button" onClick={() => controlDetector("stop")} disabled={detectorBusy}>
                Stop Native Camera
              </button>
            </div>
            <EmbeddedLivePlayer streaming={isStreaming} onToggleStream={() => setIsStreaming(!isStreaming)} />
          </div>
        </section>
      )}

      {/* RADAR & RF SCOPE TAB */}
      {activePage === "radar" && (
        <section className="page-stack">
          <div className="content-grid content-grid--overview">
            <section className="panel panel--stack">
              <RadarScope radarTracks={sensorTelemetry?.radar_tracks || []} />
            </section>
            <section className="panel panel--stack">
              <RFSpectrumWidget rfSignals={sensorTelemetry?.rf_signals || []} />
            </section>
          </div>
        </section>
      )}

      {/* C-UAS DEFENSE TAB */}
      {activePage === "countermeasures" && (
        <section className="page-stack">
          <CountermeasureStation
            onTrigger={handleTriggerCountermeasure}
            activeActions={countermeasures}
          />
        </section>
      )}

      {/* INCIDENTS TAB */}
      {activePage === "incidents" && (
        <section className="page-stack">
          <section className="panel panel--stack">
            <SectionHeader
              eyebrow="Incident Logs"
              title="Recent Security Incursions"
              meta={`${filteredAlerts.length} events`}
              action={
                <div className="toolbar-actions">
                  <input
                    className="toolbar-search"
                    type="search"
                    placeholder="Search incident..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                  <select
                    className="toolbar-select"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                  >
                    <option value="all">All Severities</option>
                    <option value="critical">Critical</option>
                    <option value="high">High</option>
                    <option value="medium">Medium</option>
                    <option value="low">Low</option>
                  </select>
                </div>
              }
            />
            <div className="alerts-stack">
              {filteredAlerts.length === 0 ? (
                <p className="muted">No security incidents match the filter.</p>
              ) : (
                filteredAlerts.map((ev) => (
                  <article key={ev.event_id} className="alert-card">
                    <div className="alert-card__head">
                      <div>
                        <div className="alert-card__meta">
                          <span>{formatTimestamp(ev.timestamp_utc)}</span>
                          <span>{ev.site_name}</span>
                        </div>
                        <h4>{ev.alerts?.[0]?.class_name?.toUpperCase() ?? "UNKNOWN"} Incursion - {ev.event_id}</h4>
                      </div>
                      <span className={`severity-pill severity-pill--${ev.alerts?.[0]?.severity || "medium"}`}>
                        {ev.alerts?.[0]?.severity || "medium"}
                      </span>
                    </div>
                    {ev.evidence_url && (
                      <img className="evidence-image" src={ev.evidence_url} alt={ev.event_id} />
                    )}
                  </article>
                ))
              )}
            </div>
          </section>
        </section>
      )}

      {/* ANALYTICS TAB */}
      {activePage === "analytics" && (
        <section className="page-stack">
          <section className="panel panel--stack">
            <SectionHeader eyebrow="Telemetry Analytics" title="Threat Distribution & Breakdown" meta="Operational History" />
            <div className="small-grid">
              <section className="mini-panel">
                <h4>Zone Incursions</h4>
                <MetricList items={analytics?.zone_breakdown} emptyText="No zone intrusions recorded." />
              </section>
              <section className="mini-panel">
                <h4>Severity Distribution</h4>
                <MetricList items={analytics?.severity_breakdown} emptyText="No severity data." />
              </section>
            </div>
          </section>
        </section>
      )}

      {/* DEMO LAB TAB */}
      {activePage === "demo" && (
        <section className="page-stack">
          <section className="panel panel--stack">
            <SectionHeader eyebrow="Simulation Engine" title="Demo Scenario Replay" meta="Offline Testing" />
            <div className="demo-controls">
              <select className="toolbar-select" value={demoSample} onChange={(e) => setDemoSample(e.target.value)}>
                {demoScenarios.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <button className="control-button" type="button" onClick={handleRunDemo} disabled={demoBusy}>
                {demoBusy ? "Processing..." : "Execute Simulation"}
              </button>
            </div>
            {demoResult && (
              <div className="demo-result">
                <img className="evidence-image evidence-image--large" src={demoResult.annotated_image_url} alt="Demo result" />
              </div>
            )}
          </section>
        </section>
      )}
    </main>
  );
}
