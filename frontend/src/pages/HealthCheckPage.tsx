import { useCallback, useEffect, useState } from "react";
import type {
  BrowserClientTelemetry,
  ChainHealthReport,
  TierNodeHealth,
} from "../types/health";

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const idx = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1
  );
  const value = bytes / Math.pow(1024, idx);
  return `${value.toFixed(idx >= 2 ? 2 : 0)} ${units[idx]}`;
}

function formatUptime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const parts: string[] = [];
  if (days > 0) parts.push(`${days}j`);
  if (hours > 0 || days > 0) parts.push(`${hours}h`);
  if (minutes > 0 || hours > 0 || days > 0) parts.push(`${minutes}m`);
  parts.push(`${secs}s`);
  return parts.join(" ");
}

function gaugeColorClass(percent: number): string {
  if (percent >= 85) return "high";
  if (percent >= 65) return "medium";
  return "low";
}

function detectBrowserName(ua: string): string {
  if (ua.includes("Edg/")) return "Microsoft Edge";
  if (ua.includes("Firefox/")) return "Mozilla Firefox";
  if (ua.includes("Chrome/")) return "Google Chrome";
  if (ua.includes("Safari/")) return "Apple Safari";
  return "Navigateur Web Standard";
}

function collectBrowserTelemetry(roundTripMs: number): BrowserClientTelemetry {
  const nav = window.navigator as Navigator & { deviceMemory?: number };
  return {
    userAgent: nav.userAgent,
    browserName: detectBrowserName(nav.userAgent),
    platformOs: nav.platform || "Plateforme Client",
    logicalCores: nav.hardwareConcurrency || 1,
    deviceMemoryGb: nav.deviceMemory ? `~${nav.deviceMemory} GB` : "Non exposé",
    screenResolution: `${window.screen.width} × ${window.screen.height}`,
    viewportSize: `${window.innerWidth} × ${window.innerHeight}`,
    pixelRatio: window.devicePixelRatio || 1,
    language: nav.language || "fr-FR",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    online: nav.onLine,
    roundTripMs: Math.round(roundTripMs * 100) / 100,
  };
}

function aggregateInstancesStatus(
  instances: TierNodeHealth[]
): "healthy" | "degraded" | "unhealthy" {
  if (instances.length === 0) return "degraded";
  if (instances.every((i) => i.status === "healthy")) return "healthy";
  if (instances.every((i) => i.status === "unhealthy")) return "unhealthy";
  return "degraded";
}

function formatInstancesSummary(
  instances: TierNodeHealth[],
  fallbackHost: string
): string {
  if (instances.length === 0) return fallbackHost;
  if (instances.length === 1) return instances[0].software.hostname;
  const hosts = instances.map((i) => i.software.hostname).join(", ");
  return `${instances.length} instances (${hosts})`;
}

function TierCard({ tier }: { tier: TierNodeHealth }) {
  const { hardware, software } = tier;
  const detailEntries = Object.entries(software.details || {});

  return (
    <article
      className="tier-card"
      data-testid={`tier-card-${tier.tier_id}-${tier.instance_id ?? software.hostname}`}
    >
      <header className="tier-card-header">
        <div>
          <h3 className="tier-name">{tier.tier_label}</h3>
          <div className="tier-service-sub">
            {software.service_name} — {software.service_version}
          </div>
          <div
            style={{
              fontSize: "0.76rem",
              color: "#94a3b8",
              marginTop: "0.2rem",
              fontFamily: "monospace",
            }}
          >
            Instance : {tier.instance_id || software.hostname}
          </div>
        </div>
        <span className={`status-pill ${tier.status}`}>
          <span className="pulse-dot" />
          {tier.status} ({tier.latency_ms} ms)
        </span>
      </header>

      {tier.error_message && (
        <div className="error-banner">{tier.error_message}</div>
      )}

      {/* Hardware Telemetry */}
      <section className="sub-box">
        <div className="sub-box-title">
          <span>Caractéristiques Hardware</span>
          <span>
            {hardware.cpu_physical_cores}C / {hardware.cpu_logical_cores}T
          </span>
        </div>

        <div style={{ fontSize: "0.8rem", color: "#cbd5e1", marginBottom: "0.85rem" }}>
          <strong>CPU :</strong> {hardware.cpu_model}
        </div>

        <div className="gauge-row">
          <div className="gauge-labels">
            <span>Charge CPU</span>
            <strong>{hardware.cpu_usage_percent.toFixed(1)}%</strong>
          </div>
          <div className="gauge-track">
            <div
              className={`gauge-fill ${gaugeColorClass(hardware.cpu_usage_percent)}`}
              style={{ width: `${Math.min(100, hardware.cpu_usage_percent)}%` }}
            />
          </div>
        </div>

        <div className="gauge-row">
          <div className="gauge-labels">
            <span>
              Mémoire RAM ({formatBytes(hardware.memory_used_bytes)} /{" "}
              {formatBytes(hardware.memory_total_bytes)})
            </span>
            <strong>{hardware.memory_usage_percent.toFixed(1)}%</strong>
          </div>
          <div className="gauge-track">
            <div
              className={`gauge-fill ${gaugeColorClass(hardware.memory_usage_percent)}`}
              style={{ width: `${Math.min(100, hardware.memory_usage_percent)}%` }}
            />
          </div>
        </div>

        <div className="gauge-row">
          <div className="gauge-labels">
            <span>
              Stockage Disque ({formatBytes(hardware.disk_used_bytes)} /{" "}
              {formatBytes(hardware.disk_total_bytes)})
            </span>
            <strong>{hardware.disk_usage_percent.toFixed(1)}%</strong>
          </div>
          <div className="gauge-track">
            <div
              className={`gauge-fill ${gaugeColorClass(hardware.disk_usage_percent)}`}
              style={{ width: `${Math.min(100, hardware.disk_usage_percent)}%` }}
            />
          </div>
        </div>
      </section>

      {/* Software Telemetry */}
      <section className="sub-box">
        <div className="sub-box-title">
          <span>Caractéristiques Software &amp; OS</span>
          <span>Uptime : {formatUptime(software.uptime_seconds)}</span>
        </div>

        <div className="kv-grid">
          <div className="kv-item">
            <span className="kv-label">Hostname Conteneur</span>
            <span className="kv-value">{software.hostname}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Système OS</span>
            <span className="kv-value">{software.os_name}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Kernel / Release</span>
            <span className="kv-value">{software.os_release}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Architecture</span>
            <span className="kv-value">{software.architecture}</span>
          </div>
          {detailEntries.map(([key, val]) => (
            <div className="kv-item" key={key}>
              <span className="kv-label">{key.replace(/_/g, " ")}</span>
              <span className="kv-value">{val}</span>
            </div>
          ))}
        </div>
      </section>
    </article>
  );
}

export function HealthCheckPage() {
  const [report, setReport] = useState<ChainHealthReport | null>(null);
  const [browserInfo, setBrowserInfo] = useState<BrowserClientTelemetry>(() =>
    collectBrowserTelemetry(0)
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [refreshIntervalSec, setRefreshIntervalSec] = useState<number>(5);

  const runHealthCheck = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    const t0 = performance.now();
    try {
      const response = await fetch("/api/health-check", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Erreur HTTP ${response.status} (${response.statusText})`);
      }
      const data = (await response.json()) as ChainHealthReport;
      const rtt = performance.now() - t0;
      setReport(data);
      setBrowserInfo(collectBrowserTelemetry(rtt));
    } catch (err) {
      const rtt = performance.now() - t0;
      setBrowserInfo(collectBrowserTelemetry(rtt));
      setFetchError(
        err instanceof Error
          ? err.message
          : "Impossible de joindre l'API /api/health-check"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void runHealthCheck();
  }, [runHealthCheck]);

  useEffect(() => {
    if (refreshIntervalSec <= 0) return undefined;
    const timer = window.setInterval(() => {
      void runHealthCheck();
    }, refreshIntervalSec * 1000);
    return () => window.clearInterval(timer);
  }, [refreshIntervalSec, runHealthCheck]);

  const presentationInstances =
    report?.tiers.filter((t) => t.tier_id === "presentation") ?? [];
  const businessInstances =
    report?.tiers.filter((t) => t.tier_id === "business") ?? [];
  const dataInstances =
    report?.tiers.filter((t) => t.tier_id === "data") ?? [];

  const presStatus = aggregateInstancesStatus(presentationInstances);
  const bizStatus = aggregateInstancesStatus(businessInstances);
  const dataStatus = aggregateInstancesStatus(dataInstances);

  return (
    <div className="dashboard-container">
      {/* Top Bar */}
      <header className="topbar">
        <div className="brand-section">
          <h1>
            <span>Diagnostic &amp; Health Check 3-Tiers</span>
            {report && (
              <span className={`status-pill ${report.overall_status}`}>
                <span className="pulse-dot" />
                Chaîne : {report.overall_status} ({report.tiers.length} conteneurs)
              </span>
            )}
          </h1>
          <p className="brand-subtitle">
            {report
              ? `${report.app_name} • Environnement : ${report.environment} • Instances : ${presentationInstances.length} Prés. / ${businessInstances.length} Bus. / ${dataInstances.length} Data • Latence cumulée : ${report.total_latency_ms} ms • RTT Navigateur : ${browserInfo.roundTripMs} ms`
              : "Vérification de la chaîne de liaison Navigateur ➔ Présentation ➔ Business ➔ Data"}
          </p>
        </div>

        <div className="controls-bar">
          <label htmlFor="auto-refresh-select" style={{ fontSize: "0.84rem", color: "#94a3b8" }}>
            Auto-refresh :
          </label>
          <select
            id="auto-refresh-select"
            className="select-refresh"
            value={refreshIntervalSec}
            onChange={(e) => setRefreshIntervalSec(Number(e.target.value))}
          >
            <option value={0}>Manuel (Désactivé)</option>
            <option value={2}>Toutes les 2s</option>
            <option value={5}>Toutes les 5s</option>
            <option value={10}>Toutes les 10s</option>
            <option value={30}>Toutes les 30s</option>
          </select>

          <button
            type="button"
            className="btn-refresh"
            onClick={() => void runHealthCheck()}
            disabled={loading}
          >
            {loading ? "Vérification en cours..." : "Rafraîchir maintenant"}
          </button>
        </div>
      </header>

      {fetchError && (
        <div className="error-banner" style={{ marginBottom: "1.5rem" }}>
          <strong>Alerte de liaison :</strong> {fetchError}
        </div>
      )}

      {/* Visualisation de la Chaîne de Liaison */}
      <section className="section-card">
        <div className="section-header">
          <h2 className="section-title">
            Chaîne de Liaison de Bout-en-Bout (Navigateur ➔ 3 Tiers Multi-Instances)
          </h2>
          {report && (
            <span style={{ fontSize: "0.8rem", color: "#94a3b8", fontFamily: "monospace" }}>
              Dernier contrôle UTC : {new Date(report.checked_at_iso).toLocaleString("fr-FR")}
            </span>
          )}
        </div>

        <div className="chain-topology">
          {/* Node 0: Browser */}
          <div className="topology-node">
            <div className="topology-node-title">Poste Client (Navigateur)</div>
            <div className="topology-node-host">{browserInfo.browserName}</div>
            <span className={`status-pill ${browserInfo.online ? "healthy" : "unhealthy"}`}>
              <span className="pulse-dot" />
              {browserInfo.online ? "EN LIGNE" : "HORS LIGNE"}
            </span>
          </div>

          {/* Link 1: Browser -> Presentation */}
          <div className="topology-connector">
            <span className="connector-protocol">HTTP GET /api/health-check</span>
            <div className={`connector-line ${fetchError ? "disconnected" : ""}`} />
            <span className="connector-latency">RTT {browserInfo.roundTripMs} ms</span>
          </div>

          {/* Node 1: Presentation */}
          <div className="topology-node">
            <div className="topology-node-title">
              Tiers 1 : Présentation ({presentationInstances.length || 1} inst.)
            </div>
            <div className="topology-node-host">
              {formatInstancesSummary(
                presentationInstances,
                "mamtemplate-presentation"
              )}
            </div>
            <span className={`status-pill ${presStatus}`}>
              <span className="pulse-dot" />
              {presStatus}
            </span>
          </div>

          {/* Link 2: Presentation -> Business */}
          <div className="topology-connector">
            <span className="connector-protocol">
              {report?.links[1]?.protocol ?? "presentation_net :8000"}
            </span>
            <div
              className={`connector-line ${
                report?.links[1]?.status === "disconnected" ? "disconnected" : ""
              }`}
            />
            <span className="connector-latency">
              {report?.links[1] ? `${report.links[1].latency_ms} ms` : "—"}
            </span>
          </div>

          {/* Node 2: Business */}
          <div className="topology-node">
            <div className="topology-node-title">
              Tiers 2 : Business ({businessInstances.length || 1} inst.)
            </div>
            <div className="topology-node-host">
              {formatInstancesSummary(businessInstances, "mamtemplate-business")}
            </div>
            <span className={`status-pill ${bizStatus}`}>
              <span className="pulse-dot" />
              {bizStatus}
            </span>
          </div>

          {/* Link 3: Business -> Data */}
          <div className="topology-connector">
            <span className="connector-protocol">
              {report?.links[2]?.protocol ?? "data_net :5432"}
            </span>
            <div
              className={`connector-line ${
                report?.links[2]?.status === "disconnected" ? "disconnected" : ""
              }`}
            />
            <span className="connector-latency">
              {report?.links[2] ? `${report.links[2].latency_ms} ms` : "—"}
            </span>
          </div>

          {/* Node 3: Data */}
          <div className="topology-node">
            <div className="topology-node-title">
              Tiers 3 : Data ({dataInstances.length || 1} inst.)
            </div>
            <div className="topology-node-host">
              {formatInstancesSummary(dataInstances, "mamtemplate-data")}
            </div>
            <span className={`status-pill ${dataStatus}`}>
              <span className="pulse-dot" />
              {dataStatus}
            </span>
          </div>
        </div>
      </section>

      {/* Cartes de tous les conteneurs de chacun des 3 Tiers */}
      {report && (
        <section className="tiers-grid">
          {report.tiers.map((tier, idx) => (
            <TierCard
              key={tier.instance_id || `${tier.tier_id}-${idx}`}
              tier={tier}
            />
          ))}
        </section>
      )}

      {/* Carte Poste Client / Navigateur */}
      <section className="section-card">
        <div className="section-header">
          <h2 className="section-title">
            Caractéristiques Hardware &amp; Software du Poste Client (Navigateur Utilisateur)
          </h2>
          <span className="status-pill healthy">
            <span className="pulse-dot" />
            RTT Bout-en-Bout : {browserInfo.roundTripMs} ms
          </span>
        </div>

        <div className="kv-grid">
          <div className="kv-item">
            <span className="kv-label">Navigateur Détecté</span>
            <span className="kv-value">{browserInfo.browserName}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Plateforme / OS Client</span>
            <span className="kv-value">{browserInfo.platformOs}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Cœurs CPU Logiques (Navigator)</span>
            <span className="kv-value">{browserInfo.logicalCores} threads</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Mémoire Appareil (Device Memory)</span>
            <span className="kv-value">{browserInfo.deviceMemoryGb}</span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Résolution Écran / Viewport</span>
            <span className="kv-value">
              {browserInfo.screenResolution} (Viewport {browserInfo.viewportSize} @{browserInfo.pixelRatio}x)
            </span>
          </div>
          <div className="kv-item">
            <span className="kv-label">Langue &amp; Fuseau Horaire</span>
            <span className="kv-value">
              {browserInfo.language} • {browserInfo.timeZone}
            </span>
          </div>
          <div className="kv-item" style={{ gridColumn: "1 / -1" }}>
            <span className="kv-label">User-Agent Complet</span>
            <span className="kv-value">{browserInfo.userAgent}</span>
          </div>
        </div>
      </section>
    </div>
  );
}
export default HealthCheckPage;
