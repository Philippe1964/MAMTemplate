"""Infrastructure tests for HealthCheckRepositoryImpl using in-memory SQLite and mocked HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

from mamtemplate.infrastructure.monitoring.health.health_check_repository_impl import (
    HealthCheckRepositoryImpl,
)
from mamtemplate.infrastructure.persistence.session import (
    create_db_engine,
    create_session_factory,
)


async def test_probe_business_and_sqlite_data_tiers() -> None:
    """Verify HealthCheckRepositoryImpl probes Business and SQLite Data tiers accurately."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    factory = create_session_factory(engine)

    async with factory() as session:
        repo = HealthCheckRepositoryImpl(
            session=session,
            presentation_metrics_url="http://127.0.0.1:9/unreachable",
        )
        business_health = await repo.probe_business_tier()
        assert business_health.tier_id == "business"
        assert business_health.status == "healthy"
        assert business_health.hardware.cpu_logical_cores >= 1
        assert "Python" in business_health.software.service_version

        data_health = await repo.probe_data_tier()
        assert data_health.tier_id == "data"
        assert data_health.status == "healthy"
        assert "SQLite" in data_health.software.service_version

        pres_fallback = await repo.probe_presentation_tier(
            forwarded_headers={"x-presentation-tier": "nginx/1.27.0"},
        )
        assert pres_fallback.tier_id == "presentation"
        assert pres_fallback.status == "healthy"

    await engine.dispose()


async def test_probe_presentation_tier_with_live_json_payload() -> None:
    """Verify probe_presentation_tier parses container JSON metrics from Presentation tier."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    factory = create_session_factory(engine)

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "hardware": {
            "cpu_model": "AMD EPYC",
            "cpu_logical_cores": 4,
            "cpu_physical_cores": 2,
            "cpu_usage_percent": 4.2,
            "memory_total_bytes": 8_000_000_000,
            "memory_used_bytes": 1_000_000_000,
            "memory_usage_percent": 12.5,
            "disk_total_bytes": 50_000_000_000,
            "disk_used_bytes": 5_000_000_000,
            "disk_usage_percent": 10.0,
        },
        "software": {
            "hostname": "mamtemplate-presentation",
            "os_name": "Alpine Linux v3.20",
            "os_release": "6.6.12",
            "architecture": "x86_64",
            "service_name": "Nginx 1.27 Reverse Proxy + React 19",
            "service_version": "nginx/1.27.4",
            "uptime_seconds": 120.5,
            "details": {"worker_processes": "auto"},
        },
    }

    async with factory() as session:
        repo = HealthCheckRepositoryImpl(
            session=session,
            presentation_metrics_url="http://mamtemplate-presentation:80/internal/presentation-metrics.json",
        )
        with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=mock_response)):
            pres_health = await repo.probe_presentation_tier(
                forwarded_headers={"x-real-ip": "172.18.0.1"},
            )

        assert pres_health.status == "healthy"
        assert pres_health.software.hostname == "mamtemplate-presentation"
        assert pres_health.hardware.cpu_model == "AMD EPYC"
        assert dict(pres_health.software.details)["client_real_ip"] == "172.18.0.1"

    await engine.dispose()


async def test_probe_all_business_instances_discovers_peer_replicas() -> None:
    """Verify probe_all_business_instances queries peer replicas discovered via DNS."""
    engine = create_db_engine("sqlite+aiosqlite:///:memory:")
    factory = create_session_factory(engine)

    peer_response = MagicMock()
    peer_response.raise_for_status.return_value = None
    peer_response.json.return_value = {
        "status": "healthy",
        "hardware": {
            "cpu_model": "AMD EPYC",
            "cpu_logical_cores": 4,
            "cpu_physical_cores": 2,
            "cpu_usage_percent": 9.5,
            "memory_total_bytes": 8_000_000_000,
            "memory_used_bytes": 2_000_000_000,
            "memory_usage_percent": 25.0,
            "disk_total_bytes": 50_000_000_000,
            "disk_used_bytes": 5_000_000_000,
            "disk_usage_percent": 10.0,
        },
        "software": {
            "hostname": "mamtemplate-business-peer-2",
            "os_name": "Alpine Linux v3.24",
            "os_release": "6.6.12",
            "architecture": "x86_64",
            "service_name": "Python 3.14 / FastAPI (Architecture 4 Couches)",
            "service_version": "Python 3.14.8",
            "uptime_seconds": 300.0,
            "details": {"process_pid": "42"},
        },
    }

    async with factory() as session:
        repo = HealthCheckRepositoryImpl(
            session=session,
            presentation_metrics_url="http://mamtemplate-presentation:80/internal/presentation-metrics.json",
            business_service_host="mamtemplate-business",
            business_service_port=8000,
        )
        with (
            patch(
                "mamtemplate.infrastructure.monitoring.health.health_check_repository_impl._resolve_service_ips",
                return_value=["10.254.0.10", "10.254.0.11"],
            ),
            patch(
                "mamtemplate.infrastructure.monitoring.health.health_check_repository_impl._get_local_ipv4_addresses",
                return_value={"127.0.0.1", "10.254.0.10"},
            ),
            patch("httpx.AsyncClient.get", new=AsyncMock(return_value=peer_response)),
        ):
            biz_instances = await repo.probe_all_business_instances()

        assert len(biz_instances) == 2
        assert any("Instance #1/2" in inst.tier_label for inst in biz_instances)
        assert any("Instance #2/2" in inst.tier_label for inst in biz_instances)
        assert any(
            inst.software.hostname == "mamtemplate-business-peer-2" for inst in biz_instances
        )

    await engine.dispose()
