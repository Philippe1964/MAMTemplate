"""Acceptance tests for the HealthApplicationService use cases."""

from unittest.mock import AsyncMock

import pytest

from mamtemplate.application.health.health_service import (
    ApplicationConfigurationError,
    CheckChainHealthRequestDto,
    CheckChainHealthResponseDto,
    CheckHealthRequestDto,
    CheckHealthResponseDto,
    HealthApplicationService,
)
from mamtemplate.domain.health.models import (
    HardwareMetrics,
    SoftwareMetrics,
    TierNodeHealth,
)
from mamtemplate.domain.health.repositories import HealthCheckRepository


def _sample_tier(tier_id: str, label: str) -> TierNodeHealth:
    """Build a sample TierNodeHealth for application acceptance tests."""
    return TierNodeHealth(
        tier_id=tier_id,
        tier_label=label,
        status="healthy",
        latency_ms=1.25,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=HardwareMetrics(
            cpu_model="Test CPU",
            cpu_logical_cores=4,
            cpu_physical_cores=2,
            cpu_usage_percent=12.5,
            memory_total_bytes=8_000_000_000,
            memory_used_bytes=2_000_000_000,
            memory_usage_percent=25.0,
            disk_total_bytes=64_000_000_000,
            disk_used_bytes=16_000_000_000,
            disk_usage_percent=25.0,
        ),
        software=SoftwareMetrics(
            hostname=f"mamtemplate-{tier_id}",
            os_name="Linux",
            os_release="6.6",
            architecture="x86_64",
            service_name=label,
            service_version="1.0",
            uptime_seconds=600.0,
            details=(("role", tier_id),),
        ),
    )


async def test_check_health_use_case() -> None:
    """Verify that check_health returns the expected CheckHealthResponseDto."""
    service = HealthApplicationService(app_name="TestApp", environment="testing")
    response = await service.check_health(CheckHealthRequestDto())

    assert isinstance(response, CheckHealthResponseDto)
    assert response.status == "ok"
    assert response.app_name == "TestApp"
    assert response.environment == "testing"


async def test_check_chain_health_use_case_orchestrates_all_3_tiers() -> None:
    """Verify check_chain_health probes all 3 tiers and returns CheckChainHealthResponseDto."""
    mock_repo = AsyncMock(spec=HealthCheckRepository)
    mock_repo.probe_all_presentation_instances.return_value = [
        _sample_tier("presentation", "Presentation #1/2"),
        _sample_tier("presentation", "Presentation #2/2"),
    ]
    mock_repo.probe_all_business_instances.return_value = [
        _sample_tier("business", "Business #1/2"),
        _sample_tier("business", "Business #2/2"),
    ]
    mock_repo.probe_all_data_instances.return_value = [
        _sample_tier("data", "Data"),
    ]

    service = HealthApplicationService(
        app_name="MAMTemplate API",
        environment="production",
        repository=mock_repo,
    )
    response = await service.check_chain_health(
        CheckChainHealthRequestDto(forwarded_headers={"x-real-ip": "10.0.0.1"}),
    )

    assert isinstance(response, CheckChainHealthResponseDto)
    assert response.overall_status == "healthy"
    assert len(response.tiers) == 5
    assert [t.tier_id for t in response.tiers] == [
        "presentation",
        "presentation",
        "business",
        "business",
        "data",
    ]
    assert len(response.links) == 3
    mock_repo.probe_all_presentation_instances.assert_awaited_once_with(
        forwarded_headers={"x-real-ip": "10.0.0.1"},
    )
    mock_repo.probe_all_business_instances.assert_awaited_once()
    mock_repo.probe_all_data_instances.assert_awaited_once()


async def test_check_chain_health_raises_when_repository_missing() -> None:
    """Verify check_chain_health raises ApplicationConfigurationError if repository is None."""
    service = HealthApplicationService(app_name="TestApp", environment="testing")
    with pytest.raises(ApplicationConfigurationError, match="HealthCheckRepository is required"):
        await service.check_chain_health(CheckChainHealthRequestDto())
