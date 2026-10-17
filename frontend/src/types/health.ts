export interface HardwareMetrics {
  cpu_model: string;
  cpu_logical_cores: number;
  cpu_physical_cores: number;
  cpu_usage_percent: number;
  memory_total_bytes: number;
  memory_used_bytes: number;
  memory_usage_percent: number;
  disk_total_bytes: number;
  disk_used_bytes: number;
  disk_usage_percent: number;
}

export interface SoftwareMetrics {
  hostname: string;
  os_name: string;
  os_release: string;
  architecture: string;
  service_name: string;
  service_version: string;
  uptime_seconds: number;
  details: Record<string, string>;
}

export interface TierNodeHealth {
  tier_id: "presentation" | "business" | "data" | string;
  tier_label: string;
  instance_id?: string;
  status: "healthy" | "degraded" | "unhealthy";
  latency_ms: number;
  checked_at_iso: string;
  hardware: HardwareMetrics;
  software: SoftwareMetrics;
  error_message: string | null;
}

export interface ChainLinkStatus {
  source_tier: string;
  target_tier: string;
  protocol: string;
  status: "connected" | "degraded" | "disconnected";
  latency_ms: number;
  details: string;
}

export interface ChainHealthReport {
  overall_status: "healthy" | "degraded" | "unhealthy";
  app_name: string;
  environment: string;
  checked_at_iso: string;
  total_latency_ms: number;
  tiers: TierNodeHealth[];
  links: ChainLinkStatus[];
}

export interface BrowserClientTelemetry {
  userAgent: string;
  browserName: string;
  platformOs: string;
  logicalCores: number;
  deviceMemoryGb: string;
  screenResolution: string;
  viewportSize: string;
  pixelRatio: number;
  language: string;
  timeZone: string;
  online: boolean;
  roundTripMs: number;
}
