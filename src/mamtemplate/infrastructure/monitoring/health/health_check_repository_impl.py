"""Infrastructure implementation of HealthCheckRepository across 1..N instances per tier."""

from __future__ import annotations

import asyncio
import datetime
import importlib.metadata
import json
import os
import platform
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import psutil
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mamtemplate.domain.health.models import (
    HardwareMetrics,
    SoftwareMetrics,
    TierNodeHealth,
)


def _utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format.

    Returns:
        ISO-8601 UTC timestamp string.
    """
    return datetime.datetime.now(datetime.UTC).isoformat()


def _clamp_percent(value: float) -> float:
    """Clamp a percentage value to the [0.0, 100.0] interval.

    Args:
        value: Raw percentage float.

    Returns:
        Clamped float rounded to 2 decimal places.
    """
    return round(min(max(float(value), 0.0), 100.0), 2)


def _detect_cpu_model() -> str:
    """Detect the CPU model name across Linux containers and Windows/macOS hosts.

    Returns:
        Human-readable CPU model string.
    """
    cpuinfo_path = Path("/proc/cpuinfo")
    if cpuinfo_path.is_file():
        try:
            content = cpuinfo_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    if (
                        key.strip().lower() in {"model name", "hardware", "processor"}
                        and val.strip()
                    ):
                        candidate = val.strip()
                        if not candidate.isdigit():
                            return candidate
        except OSError:
            pass
    proc = platform.processor().strip()
    if proc:
        return proc
    return f"{platform.machine()} Processor"


def _detect_pretty_os_name() -> str:
    """Detect the operating system pretty name (including Linux distribution in containers).

    Returns:
        Human-readable operating system name and version.
    """
    os_release_path = Path("/etc/os-release")
    if os_release_path.is_file():
        try:
            for line in os_release_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.partition("=")[2].strip().strip('"').strip("'")
        except OSError:
            pass
    return f"{platform.system()} {platform.release()}"


def _collect_local_hardware_metrics() -> HardwareMetrics:
    """Collect hardware metrics from the current host or container using psutil.

    Returns:
        Populated HardwareMetrics value object.
    """
    logical_cores = psutil.cpu_count(logical=True) or 1
    physical_cores = psutil.cpu_count(logical=False) or logical_cores
    cpu_percent = _clamp_percent(psutil.cpu_percent(interval=None))
    vm = psutil.virtual_memory()
    disk_root = Path.cwd().anchor or "/"
    disk = psutil.disk_usage(disk_root)

    return HardwareMetrics(
        cpu_model=_detect_cpu_model(),
        cpu_logical_cores=max(1, logical_cores),
        cpu_physical_cores=max(1, physical_cores),
        cpu_usage_percent=cpu_percent,
        memory_total_bytes=max(0, int(vm.total)),
        memory_used_bytes=max(0, int(vm.used)),
        memory_usage_percent=_clamp_percent(vm.percent),
        disk_total_bytes=max(0, int(disk.total)),
        disk_used_bytes=max(0, int(disk.used)),
        disk_usage_percent=_clamp_percent(disk.percent),
    )


def _get_package_version(package_name: str) -> str:
    """Safely look up an installed Python package version.

    Args:
        package_name: Distribution package name.

    Returns:
        Package version string or 'unknown'.
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _resolve_service_ips(host: str, port: int) -> list[str]:
    """Resolve all IPv4 addresses registered in Docker DNS for a given service hostname.

    Args:
        host: Service hostname or alias (e.g. 'mamtemplate-business').
        port: Service TCP port.

    Returns:
        Sorted list of unique IPv4 address strings, or empty list if resolution fails.
    """
    try:
        infos = socket.getaddrinfo(host, port, family=socket.AF_INET, type=socket.SOCK_STREAM)
        ips = {str(info[4][0]) for info in infos if info[4]}
        return sorted(ips)
    except OSError:
        return []


def _get_local_ipv4_addresses() -> set[str]:
    """Return all IPv4 addresses bound to the current container/host network interfaces.

    Returns:
        Set of local IPv4 address strings.
    """
    local_ips: set[str] = {"127.0.0.1"}
    try:
        for iface_addrs in psutil.net_if_addrs().values():
            for snic in iface_addrs:
                if snic.family == socket.AF_INET and snic.address:
                    local_ips.add(snic.address)
    except OSError:
        return local_ips
    return local_ips


class HealthCheckRepositoryImpl:
    """Concrete infrastructure repository probing all Presentation, Business, and Data instances."""

    def __init__(
        self,
        session: AsyncSession,
        presentation_metrics_url: str,
        business_service_host: str = "mamtemplate-business",
        business_service_port: int = 8000,
    ) -> None:
        """Initialize the repository with database session and multi-replica discovery config.

        Args:
            session: SQLAlchemy AsyncSession for probing the Data tier.
            presentation_metrics_url: Internal HTTP URL exposing Presentation container metrics.
            business_service_host: DNS service name/alias for discovering Business replicas.
            business_service_port: Internal TCP port of Business replicas.
        """
        self._session = session
        self._presentation_metrics_url = presentation_metrics_url
        self._business_service_host = business_service_host
        self._business_service_port = business_service_port

    async def probe_presentation_tier(
        self,
        forwarded_headers: dict[str, str] | None = None,
    ) -> TierNodeHealth:
        """Probe a single Presentation tier instance (Nginx Reverse Proxy container).

        Args:
            forwarded_headers: Optional HTTP headers forwarded by Nginx.

        Returns:
            TierNodeHealth representing the Presentation tier state and metrics.
        """
        return await self._probe_presentation_url(
            target_url=self._presentation_metrics_url,
            forwarded_headers=forwarded_headers,
            instance_ip=None,
        )

    async def _probe_presentation_url(
        self,
        target_url: str,
        forwarded_headers: dict[str, str] | None,
        instance_ip: str | None,
    ) -> TierNodeHealth:
        """Probe a specific Presentation container URL and parse its hardware/software JSON.

        Args:
            target_url: HTTP URL of the presentation metrics JSON endpoint.
            forwarded_headers: Optional HTTP headers forwarded by Nginx.
            instance_ip: Optional resolved IPv4 address of the container replica.

        Returns:
            TierNodeHealth for that Presentation container instance.
        """
        start = time.perf_counter()
        headers_map = {k.lower(): v for k, v in (forwarded_headers or {}).items()}
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(target_url)
                response.raise_for_status()
                payload: dict[str, Any] = response.json()

            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            hw_data: dict[str, Any] = payload.get("hardware", {})
            sw_data: dict[str, Any] = payload.get("software", {})
            raw_details: dict[str, Any] = sw_data.get("details", {})

            details_list: list[tuple[str, str]] = [(str(k), str(v)) for k, v in raw_details.items()]
            if instance_ip:
                details_list.append(("container_ip", instance_ip))
            if "x-forwarded-for" in headers_map:
                details_list.append(("x_forwarded_for", headers_map["x-forwarded-for"]))
            if "x-real-ip" in headers_map:
                details_list.append(("client_real_ip", headers_map["x-real-ip"]))

            logical_cores = max(1, int(hw_data.get("cpu_logical_cores", 1)))
            physical_cores = max(1, int(hw_data.get("cpu_physical_cores", logical_cores)))

            hardware = HardwareMetrics(
                cpu_model=str(hw_data.get("cpu_model") or _detect_cpu_model()),
                cpu_logical_cores=logical_cores,
                cpu_physical_cores=physical_cores,
                cpu_usage_percent=_clamp_percent(float(hw_data.get("cpu_usage_percent", 0.0))),
                memory_total_bytes=max(0, int(hw_data.get("memory_total_bytes", 0))),
                memory_used_bytes=max(0, int(hw_data.get("memory_used_bytes", 0))),
                memory_usage_percent=_clamp_percent(
                    float(hw_data.get("memory_usage_percent", 0.0))
                ),
                disk_total_bytes=max(0, int(hw_data.get("disk_total_bytes", 0))),
                disk_used_bytes=max(0, int(hw_data.get("disk_used_bytes", 0))),
                disk_usage_percent=_clamp_percent(float(hw_data.get("disk_usage_percent", 0.0))),
            )

            host_str = str(sw_data.get("hostname") or "mamtemplate-presentation")
            software = SoftwareMetrics(
                hostname=host_str,
                os_name=str(sw_data.get("os_name") or "Alpine Linux"),
                os_release=str(sw_data.get("os_release") or platform.release()),
                architecture=str(sw_data.get("architecture") or platform.machine()),
                service_name=str(sw_data.get("service_name") or "Nginx Reverse Proxy + React 19"),
                service_version=str(sw_data.get("service_version") or "nginx/1.27"),
                uptime_seconds=max(0.0, float(sw_data.get("uptime_seconds", 0.0))),
                details=tuple(details_list),
            )

            return TierNodeHealth(
                tier_id="presentation",
                tier_label="Tiers 1 — Présentation (Nginx & React SPA)",
                status="healthy",
                latency_ms=latency_ms,
                checked_at_iso=_utc_now_iso(),
                hardware=hardware,
                software=software,
                instance_id=f"{host_str} ({instance_ip})" if instance_ip else host_str,
            )
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            fallback_hw = _collect_local_hardware_metrics()
            proxy_via = headers_map.get("x-presentation-tier")
            is_proxied = bool(proxy_via)
            host_str = headers_map.get("x-presentation-hostname", socket.gethostname())
            fallback_sw = SoftwareMetrics(
                hostname=host_str,
                os_name=_detect_pretty_os_name(),
                os_release=platform.release(),
                architecture=platform.machine(),
                service_name="Passerelle HTTP / Reverse Proxy",
                service_version=proxy_via or "Accès direct (Mode Dev Local)",
                uptime_seconds=max(0.0, time.time() - psutil.boot_time()),
                details=(
                    ("mode", "Passerelle Nginx" if is_proxied else "Direct / Hors Docker"),
                    ("probe_url", target_url),
                ),
            )
            return TierNodeHealth(
                tier_id="presentation",
                tier_label="Tiers 1 — Présentation (Nginx & React SPA)",
                status="healthy" if is_proxied else "degraded",
                latency_ms=latency_ms,
                checked_at_iso=_utc_now_iso(),
                hardware=fallback_hw,
                software=fallback_sw,
                error_message=(
                    None
                    if is_proxied
                    else (
                        f"Sonde conteneur Nginx indisponible en mode direct ({type(exc).__name__})"
                    )
                ),
                instance_id=host_str,
            )

    async def probe_all_presentation_instances(
        self,
        forwarded_headers: dict[str, str] | None = None,
    ) -> list[TierNodeHealth]:
        """Discover via DNS and probe all container instances of the Presentation tier.

        Args:
            forwarded_headers: Optional HTTP headers forwarded by Nginx.

        Returns:
            List of TierNodeHealth for every discovered Presentation container instance.
        """
        parsed = urlparse(self._presentation_metrics_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        path = parsed.path or "/internal/presentation-metrics.json"

        ips = _resolve_service_ips(host, port) if host else []
        if len(ips) <= 1:
            single = await self._probe_presentation_url(
                target_url=self._presentation_metrics_url,
                forwarded_headers=forwarded_headers,
                instance_ip=ips[0] if ips else None,
            )
            return [single]

        tasks = [
            self._probe_presentation_url(
                target_url=f"{parsed.scheme}://{ip}:{port}{path}",
                forwarded_headers=forwarded_headers,
                instance_ip=ip,
            )
            for ip in ips
        ]
        results = await asyncio.gather(*tasks)
        return _relabel_multi_instances(
            results,
            base_label="Tiers 1 — Présentation (Nginx & React SPA)",
            short_prefix="Tiers 1 — Présentation",
        )

    async def probe_business_tier(self) -> TierNodeHealth:
        """Probe the current Business tier container instance (Python 3.14 / FastAPI).

        Returns:
            TierNodeHealth representing the current Business container state and metrics.
        """
        start = time.perf_counter()
        hardware = _collect_local_hardware_metrics()

        fastapi_ver = _get_package_version("fastapi")
        pydantic_ver = _get_package_version("pydantic")
        sqlalchemy_ver = _get_package_version("sqlalchemy")
        uvicorn_ver = _get_package_version("uvicorn")

        proc = psutil.Process(os.getpid())
        proc_rss_bytes = proc.memory_info().rss
        proc_uptime = max(0.0, time.time() - proc.create_time())
        host_str = socket.gethostname()
        local_ips = sorted(ip for ip in _get_local_ipv4_addresses() if ip != "127.0.0.1")
        primary_ip = local_ips[0] if local_ips else "127.0.0.1"

        software = SoftwareMetrics(
            hostname=host_str,
            os_name=_detect_pretty_os_name(),
            os_release=platform.release(),
            architecture=platform.machine(),
            service_name="Python 3.14 / FastAPI (Architecture 4 Couches)",
            service_version=f"Python {platform.python_version()} • FastAPI {fastapi_ver}",
            uptime_seconds=round(proc_uptime, 2),
            details=(
                ("container_ip", primary_ip),
                ("python_version", platform.python_version()),
                ("fastapi_version", fastapi_ver),
                ("uvicorn_version", uvicorn_ver),
                ("pydantic_version", pydantic_ver),
                ("sqlalchemy_version", sqlalchemy_ver),
                ("process_pid", str(os.getpid())),
                ("process_rss_mb", f"{proc_rss_bytes / (1024 * 1024):.2f} MB"),
                ("system_uptime_s", f"{max(0.0, time.time() - psutil.boot_time()):.0f}s"),
            ),
        )
        latency_ms = round((time.perf_counter() - start) * 1000.0, 2)

        return TierNodeHealth(
            tier_id="business",
            tier_label="Tiers 2 — Business (Python 3.14 / FastAPI)",
            status="healthy",
            latency_ms=latency_ms,
            checked_at_iso=_utc_now_iso(),
            hardware=hardware,
            software=software,
            instance_id=f"{host_str} ({primary_ip})",
        )

    async def _probe_peer_business_instance(self, peer_ip: str) -> TierNodeHealth | None:
        """Probe a peer Business container replica via its /internal/business-metrics endpoint.

        Args:
            peer_ip: IPv4 address of the peer Business replica on presentation_net.

        Returns:
            TierNodeHealth of the peer replica, or None if unreachable.
        """
        url = f"http://{peer_ip}:{self._business_service_port}/internal/business-metrics"
        start = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload: dict[str, Any] = response.json()

            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            hw_data: dict[str, Any] = payload.get("hardware", {})
            sw_data: dict[str, Any] = payload.get("software", {})
            raw_details: dict[str, Any] = sw_data.get("details", {})
            raw_details["container_ip"] = peer_ip

            logical_cores = max(1, int(hw_data.get("cpu_logical_cores", 1)))
            physical_cores = max(1, int(hw_data.get("cpu_physical_cores", logical_cores)))

            hardware = HardwareMetrics(
                cpu_model=str(hw_data.get("cpu_model") or _detect_cpu_model()),
                cpu_logical_cores=logical_cores,
                cpu_physical_cores=physical_cores,
                cpu_usage_percent=_clamp_percent(float(hw_data.get("cpu_usage_percent", 0.0))),
                memory_total_bytes=max(0, int(hw_data.get("memory_total_bytes", 0))),
                memory_used_bytes=max(0, int(hw_data.get("memory_used_bytes", 0))),
                memory_usage_percent=_clamp_percent(
                    float(hw_data.get("memory_usage_percent", 0.0))
                ),
                disk_total_bytes=max(0, int(hw_data.get("disk_total_bytes", 0))),
                disk_used_bytes=max(0, int(hw_data.get("disk_used_bytes", 0))),
                disk_usage_percent=_clamp_percent(float(hw_data.get("disk_usage_percent", 0.0))),
            )

            host_str = str(sw_data.get("hostname") or f"business-{peer_ip}")
            software = SoftwareMetrics(
                hostname=host_str,
                os_name=str(sw_data.get("os_name") or "Alpine Linux"),
                os_release=str(sw_data.get("os_release") or platform.release()),
                architecture=str(sw_data.get("architecture") or platform.machine()),
                service_name=str(
                    sw_data.get("service_name") or "Python 3.14 / FastAPI (Architecture 4 Couches)"
                ),
                service_version=str(sw_data.get("service_version") or "Python 3.14"),
                uptime_seconds=max(0.0, float(sw_data.get("uptime_seconds", 0.0))),
                details=tuple((str(k), str(v)) for k, v in raw_details.items()),
            )
            return TierNodeHealth(
                tier_id="business",
                tier_label="Tiers 2 — Business (Python 3.14 / FastAPI)",
                status=str(payload.get("status") or "healthy"),
                latency_ms=latency_ms,
                checked_at_iso=_utc_now_iso(),
                hardware=hardware,
                software=software,
                instance_id=f"{host_str} ({peer_ip})",
            )
        except Exception:
            return None

    async def probe_all_business_instances(self) -> list[TierNodeHealth]:
        """Discover via DNS and probe all container instances of the Business tier.

        Returns:
            List of TierNodeHealth for every discovered Business container instance.
        """
        local_node = await self.probe_business_tier()
        all_ips = _resolve_service_ips(self._business_service_host, self._business_service_port)
        local_ips = _get_local_ipv4_addresses()
        peer_ips = [ip for ip in all_ips if ip not in local_ips]

        if not peer_ips:
            return [local_node]

        peer_results = await asyncio.gather(
            *(self._probe_peer_business_instance(ip) for ip in peer_ips)
        )
        valid_peers = [node for node in peer_results if node is not None]
        combined = [local_node, *valid_peers]
        return _relabel_multi_instances(
            combined,
            base_label="Tiers 2 — Business (Python 3.14 / FastAPI)",
            short_prefix="Tiers 2 — Business",
        )

    async def probe_data_tier(self) -> TierNodeHealth:
        """Probe the primary Data tier instance (PostgreSQL 17 or SQLite) via AsyncSession.

        Returns:
            TierNodeHealth representing the Data tier state and metrics.
        """
        start = time.perf_counter()
        try:
            dialect_name = self._session.get_bind().dialect.name

            if dialect_name == "postgresql":
                return await self._probe_postgresql_tier(start)
            return await self._probe_sqlite_or_generic_tier(start, dialect_name)
        except Exception as exc:
            latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
            fallback_hw = _collect_local_hardware_metrics()
            fallback_sw = SoftwareMetrics(
                hostname="mamtemplate-data",
                os_name="PostgreSQL Container",
                os_release="unknown",
                architecture=platform.machine(),
                service_name="PostgreSQL 17 (Tiers Data)",
                service_version="Injoignable",
                uptime_seconds=0.0,
                details=(("connection_error", str(exc)),),
            )
            return TierNodeHealth(
                tier_id="data",
                tier_label="Tiers 3 — Data (PostgreSQL 17)",
                status="unhealthy",
                latency_ms=latency_ms,
                checked_at_iso=_utc_now_iso(),
                hardware=fallback_hw,
                software=fallback_sw,
                error_message=f"Échec de connexion SQL au tiers Data : {exc}",
                instance_id="mamtemplate-data",
            )

    async def probe_all_data_instances(self) -> list[TierNodeHealth]:
        """Probe the primary Data tier and any attached PostgreSQL replication instances.

        Returns:
            List of TierNodeHealth for every discovered Data tier instance.
        """
        primary_node = await self.probe_data_tier()
        instances: list[TierNodeHealth] = [primary_node]

        try:
            if self._session.get_bind().dialect.name == "postgresql":
                rep_query = text(
                    """
                    SELECT
                        COALESCE(
                            client_hostname, client_addr::text, application_name
                        ) AS replica_host,
                        COALESCE(client_addr::text, 'internal') AS replica_ip,
                        state,
                        sync_state
                    FROM pg_stat_replication
                    """
                )
                rep_result = await self._session.execute(rep_query)
                for row in rep_result.mappings().all():
                    rep_host = str(row["replica_host"] or "postgres-replica")
                    rep_ip = str(row["replica_ip"] or "internal")
                    rep_state = str(row["state"] or "streaming")
                    rep_sw = SoftwareMetrics(
                        hostname=rep_host,
                        os_name=primary_node.software.os_name,
                        os_release=primary_node.software.os_release,
                        architecture=primary_node.software.architecture,
                        service_name="PostgreSQL Standby / Read-Replica",
                        service_version=primary_node.software.service_version,
                        uptime_seconds=primary_node.software.uptime_seconds,
                        details=(
                            ("role", "Standby Replica"),
                            ("replica_ip", rep_ip),
                            ("replication_state", rep_state),
                            ("sync_state", str(row["sync_state"] or "async")),
                        ),
                    )
                    instances.append(
                        TierNodeHealth(
                            tier_id="data",
                            tier_label="Tiers 3 — Data (PostgreSQL 17)",
                            status="healthy" if rep_state == "streaming" else "degraded",
                            latency_ms=primary_node.latency_ms,
                            checked_at_iso=_utc_now_iso(),
                            hardware=primary_node.hardware,
                            software=rep_sw,
                            instance_id=f"{rep_host} ({rep_ip})",
                        )
                    )
        except Exception:
            await self._session.rollback()

        return _relabel_multi_instances(
            instances,
            base_label=primary_node.tier_label,
            short_prefix="Tiers 3 — Data",
        )

    async def _probe_postgresql_tier(self, start_perf: float) -> TierNodeHealth:
        """Execute PostgreSQL-specific diagnostic queries and read container metrics.

        Args:
            start_perf: Performance counter timestamp when the probe started.

        Returns:
            TierNodeHealth populated with live PostgreSQL and container metrics.
        """
        query = text(
            """
            SELECT
                version() AS pg_version,
                current_database() AS db_name,
                current_user AS db_user,
                pg_database_size(current_database()) AS db_size_bytes,
                EXTRACT(EPOCH FROM (now() - pg_postmaster_start_time())) AS pg_uptime_seconds,
                (SELECT count(*) FROM pg_stat_activity) AS active_connections,
                current_setting('max_connections') AS max_connections,
                current_setting('server_encoding') AS server_encoding,
                current_setting('server_version') AS server_version_num,
                COALESCE(inet_server_addr()::text, 'data_net') AS server_ip
            """
        )
        result = await self._session.execute(query)
        row = result.mappings().one()

        container_hw: dict[str, Any] = {}
        container_sw: dict[str, Any] = {}
        try:
            hw_result = await self._session.execute(
                text("SELECT pg_read_file('container_metrics.json') AS raw_json")
            )
            raw_json = hw_result.scalar_one_or_none()
            if raw_json:
                parsed: dict[str, Any] = json.loads(str(raw_json))
                container_hw = parsed.get("hardware", {})
                container_sw = parsed.get("software", {})
        except Exception:
            await self._session.rollback()

        latency_ms = round((time.perf_counter() - start_perf) * 1000.0, 2)
        local_hw = _collect_local_hardware_metrics()

        logical_cores = max(
            1, int(container_hw.get("cpu_logical_cores", local_hw.cpu_logical_cores))
        )
        physical_cores = max(
            1, int(container_hw.get("cpu_physical_cores", local_hw.cpu_physical_cores))
        )

        hardware = HardwareMetrics(
            cpu_model=str(container_hw.get("cpu_model") or local_hw.cpu_model),
            cpu_logical_cores=logical_cores,
            cpu_physical_cores=physical_cores,
            cpu_usage_percent=_clamp_percent(
                float(container_hw.get("cpu_usage_percent", local_hw.cpu_usage_percent))
            ),
            memory_total_bytes=max(
                0, int(container_hw.get("memory_total_bytes", local_hw.memory_total_bytes))
            ),
            memory_used_bytes=max(
                0, int(container_hw.get("memory_used_bytes", local_hw.memory_used_bytes))
            ),
            memory_usage_percent=_clamp_percent(
                float(container_hw.get("memory_usage_percent", local_hw.memory_usage_percent))
            ),
            disk_total_bytes=max(
                0, int(container_hw.get("disk_total_bytes", local_hw.disk_total_bytes))
            ),
            disk_used_bytes=max(
                0, int(container_hw.get("disk_used_bytes", local_hw.disk_used_bytes))
            ),
            disk_usage_percent=_clamp_percent(
                float(container_hw.get("disk_usage_percent", local_hw.disk_usage_percent))
            ),
        )

        db_size_bytes = int(row["db_size_bytes"] or 0)
        db_size_mb = f"{db_size_bytes / (1024 * 1024):.2f} MB"
        pg_version_full = str(row["pg_version"] or "PostgreSQL 17")
        server_ver = str(row["server_version_num"] or "17")
        server_ip = str(row["server_ip"] or "data_net")
        host_str = str(container_sw.get("hostname") or "mamtemplate-data")

        software = SoftwareMetrics(
            hostname=host_str,
            os_name=str(container_sw.get("os_name") or _detect_pretty_os_name()),
            os_release=str(container_sw.get("os_release") or platform.release()),
            architecture=str(container_sw.get("architecture") or platform.machine()),
            service_name="PostgreSQL Relational Database",
            service_version=f"PostgreSQL {server_ver}",
            uptime_seconds=round(max(0.0, float(row["pg_uptime_seconds"] or 0.0)), 2),
            details=(
                ("container_ip", server_ip),
                ("database_name", str(row["db_name"])),
                ("database_user", str(row["db_user"])),
                ("database_size", db_size_mb),
                ("active_connections", f"{row['active_connections']} / {row['max_connections']}"),
                ("server_encoding", str(row["server_encoding"])),
                ("full_version", pg_version_full),
            ),
        )

        return TierNodeHealth(
            tier_id="data",
            tier_label="Tiers 3 — Data (PostgreSQL 17)",
            status="healthy",
            latency_ms=latency_ms,
            checked_at_iso=_utc_now_iso(),
            hardware=hardware,
            software=software,
            instance_id=f"{host_str} ({server_ip})",
        )

    async def _probe_sqlite_or_generic_tier(
        self,
        start_perf: float,
        dialect_name: str,
    ) -> TierNodeHealth:
        """Execute SQLite or generic SQL diagnostic query when running in local/test mode.

        Args:
            start_perf: Performance counter timestamp when the probe started.
            dialect_name: SQLAlchemy dialect name (e.g. 'sqlite').

        Returns:
            TierNodeHealth populated with SQLite/generic database and host metrics.
        """
        result = await self._session.execute(text("SELECT sqlite_version() AS ver"))
        sqlite_ver = str(result.scalar_one_or_none() or "3.x")
        latency_ms = round((time.perf_counter() - start_perf) * 1000.0, 2)
        hardware = _collect_local_hardware_metrics()
        host_str = socket.gethostname()
        software = SoftwareMetrics(
            hostname=host_str,
            os_name=_detect_pretty_os_name(),
            os_release=platform.release(),
            architecture=platform.machine(),
            service_name=f"SQLite ({dialect_name}) — Mode Local/Test",
            service_version=f"SQLite {sqlite_ver}",
            uptime_seconds=round(max(0.0, time.time() - psutil.boot_time()), 2),
            details=(
                ("dialect", dialect_name),
                ("sqlite_version", sqlite_ver),
            ),
        )
        return TierNodeHealth(
            tier_id="data",
            tier_label="Tiers 3 — Data (Base de Données)",
            status="healthy",
            latency_ms=latency_ms,
            checked_at_iso=_utc_now_iso(),
            hardware=hardware,
            software=software,
            instance_id=host_str,
        )


def _relabel_multi_instances(
    nodes: list[TierNodeHealth],
    base_label: str,
    short_prefix: str,
) -> list[TierNodeHealth]:
    """Deduplicate by hostname and number each container instance when a tier has multiple replicas.

    Args:
        nodes: Discovered container health nodes for one tier.
        base_label: Default label when only 1 instance is running.
        short_prefix: Prefix used when numbering multiple instances (e.g. 'Tiers 2 — Business').

    Returns:
        Deduplicated, sorted list of TierNodeHealth instances.
    """
    unique_by_key: dict[str, TierNodeHealth] = {}
    for node in nodes:
        key = node.instance_id or node.software.hostname
        unique_by_key[key] = node

    sorted_nodes = sorted(unique_by_key.values(), key=lambda n: n.instance_id)
    if len(sorted_nodes) <= 1:
        return [
            TierNodeHealth(
                tier_id=n.tier_id,
                tier_label=base_label,
                status=n.status,
                latency_ms=n.latency_ms,
                checked_at_iso=n.checked_at_iso,
                hardware=n.hardware,
                software=n.software,
                error_message=n.error_message,
                instance_id=n.instance_id,
            )
            for n in sorted_nodes
        ]

    total = len(sorted_nodes)
    return [
        TierNodeHealth(
            tier_id=n.tier_id,
            tier_label=f"{short_prefix} — Instance #{idx}/{total} ({n.software.hostname})",
            status=n.status,
            latency_ms=n.latency_ms,
            checked_at_iso=n.checked_at_iso,
            hardware=n.hardware,
            software=n.software,
            error_message=n.error_message,
            instance_id=n.instance_id,
        )
        for idx, n in enumerate(sorted_nodes, start=1)
    ]
