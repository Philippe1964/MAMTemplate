"""Presentation layer tests for the /health and /api/health-check endpoints."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from mamtemplate.application.health.health_service import (
    ChainLinkStatusDto,
    CheckChainHealthResponseDto,
    CheckHealthResponseDto,
    HardwareMetricsDto,
    HealthApplicationService,
    SoftwareMetricsDto,
    TierNodeHealthDto,
)
from mamtemplate.domain.shared.base import DomainError
from mamtemplate.presentation.api.app import create_app
from mamtemplate.presentation.health.health_router import (
    get_chain_health_service,
    get_health_service,
)


def _sample_tier_dto(tier_id: str) -> TierNodeHealthDto:
    """Build a sample TierNodeHealthDto for router contract tests."""
    return TierNodeHealthDto(
        tier_id=tier_id,
        tier_label=f"Tier {tier_id}",
        status="healthy",
        latency_ms=1.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=HardwareMetricsDto(
            cpu_model="CPU",
            cpu_logical_cores=4,
            cpu_physical_cores=2,
            cpu_usage_percent=10.0,
            memory_total_bytes=1024,
            memory_used_bytes=512,
            memory_usage_percent=50.0,
            disk_total_bytes=2048,
            disk_used_bytes=1024,
            disk_usage_percent=50.0,
        ),
        software=SoftwareMetricsDto(
            hostname=f"mamtemplate-{tier_id}",
            os_name="Linux",
            os_release="6.6",
            architecture="x86_64",
            service_name="Service",
            service_version="1.0",
            uptime_seconds=100.0,
            details={"key": "val"},
        ),
    )


def test_check_health_endpoint_returns_200() -> None:
    """Verify GET /health delegates to HealthApplicationService and returns 200 OK."""
    app = create_app()
    mock_service = AsyncMock(spec=HealthApplicationService)
    mock_service.check_health.return_value = CheckHealthResponseDto(
        status="ok",
        app_name="MAMTemplate API",
        environment="test",
    )
    app.dependency_overrides[get_health_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app_name": "MAMTemplate API",
        "environment": "test",
    }
    mock_service.check_health.assert_awaited_once()


def test_check_health_endpoint_maps_domain_error_to_400() -> None:
    """Verify GET /health catches DomainError and maps it to HTTP 400."""
    app = create_app()
    mock_service = AsyncMock(spec=HealthApplicationService)
    mock_service.check_health.side_effect = DomainError("Simulated domain failure")
    app.dependency_overrides[get_health_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 400
    assert response.json() == {"detail": "Simulated domain failure"}


def test_check_chain_health_endpoint_returns_200() -> None:
    """Verify GET /api/health-check delegates to HealthApplicationService and returns 200 OK."""
    app = create_app()
    mock_service = AsyncMock(spec=HealthApplicationService)
    mock_service.check_chain_health.return_value = CheckChainHealthResponseDto(
        overall_status="healthy",
        app_name="MAMTemplate API",
        environment="production",
        checked_at_iso="2026-10-17T12:00:00Z",
        total_latency_ms=3.0,
        tiers=[
            _sample_tier_dto("presentation"),
            _sample_tier_dto("business"),
            _sample_tier_dto("data"),
        ],
        links=[
            ChainLinkStatusDto(
                source_tier="presentation",
                target_tier="business",
                protocol="HTTP/1.1",
                status="connected",
                latency_ms=2.0,
                details="ok",
            ),
        ],
    )
    app.dependency_overrides[get_chain_health_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get("/api/health-check")

    assert response.status_code == 200
    body = response.json()
    assert body["overall_status"] == "healthy"
    assert len(body["tiers"]) == 3
    mock_service.check_chain_health.assert_awaited_once()


def test_check_chain_health_endpoint_maps_domain_error_to_400() -> None:
    """Verify GET /api/health-check catches DomainError and maps it to HTTP 400."""
    app = create_app()
    mock_service = AsyncMock(spec=HealthApplicationService)
    mock_service.check_chain_health.side_effect = DomainError("Chain probe error")
    app.dependency_overrides[get_chain_health_service] = lambda: mock_service

    client = TestClient(app)
    response = client.get("/api/health-check")

    assert response.status_code == 400
    assert response.json() == {"detail": "Chain probe error"}


def test_liveness_and_readiness_probes_and_correlation_id() -> None:
    """Verify /health/live, /health/ready, and X-Request-ID header propagation."""
    app = create_app()
    mock_service = AsyncMock(spec=HealthApplicationService)
    mock_service.check_health.return_value = CheckHealthResponseDto(
        status="ok",
        app_name="MAMTemplate API",
        environment="production",
    )
    mock_service.check_chain_health.return_value = CheckChainHealthResponseDto(
        overall_status="healthy",
        app_name="MAMTemplate API",
        environment="production",
        checked_at_iso="2026-10-17T12:00:00Z",
        total_latency_ms=2.0,
        tiers=[_sample_tier_dto("data")],
        links=[],
    )
    app.dependency_overrides[get_health_service] = lambda: mock_service
    app.dependency_overrides[get_chain_health_service] = lambda: mock_service

    client = TestClient(app)
    live_res = client.get("/health/live", headers={"X-Request-ID": "corr-001"})
    assert live_res.status_code == 200
    assert live_res.headers["X-Request-ID"] == "corr-001"

    ready_res = client.get("/health/ready")
    assert ready_res.status_code == 200
    assert ready_res.json()["status"] == "ready"
    assert "X-Request-ID" in ready_res.headers
