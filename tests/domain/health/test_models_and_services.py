"""Unit tests for Domain health value objects and HealthChainDomainService."""

import pytest

from mamtemplate.domain.health.models import (
    ChainLinkStatus,
    HardwareMetrics,
    InvalidHealthMetricError,
    SoftwareMetrics,
    TierNodeHealth,
)
from mamtemplate.domain.health.services import HealthChainDomainService


def _make_hardware(cpu_usage: float = 15.0) -> HardwareMetrics:
    """Create a valid HardwareMetrics fixture for tests."""
    return HardwareMetrics(
        cpu_model="Intel Xeon",
        cpu_logical_cores=8,
        cpu_physical_cores=4,
        cpu_usage_percent=cpu_usage,
        memory_total_bytes=16_000_000_000,
        memory_used_bytes=4_000_000_000,
        memory_usage_percent=25.0,
        disk_total_bytes=100_000_000_000,
        disk_used_bytes=20_000_000_000,
        disk_usage_percent=20.0,
    )


def _make_software(hostname: str = "node-1") -> SoftwareMetrics:
    """Create a valid SoftwareMetrics fixture for tests."""
    return SoftwareMetrics(
        hostname=hostname,
        os_name="Alpine Linux 3.20",
        os_release="6.6.0",
        architecture="x86_64",
        service_name="TestService",
        service_version="1.0.0",
        uptime_seconds=3600.0,
        details=(("env", "test"),),
    )


def test_hardware_metrics_validation_rejects_invalid_values() -> None:
    """Verify HardwareMetrics enforces core, percentage, and byte invariants."""
    with pytest.raises(InvalidHealthMetricError, match="CPU core counts"):
        HardwareMetrics(
            cpu_model="CPU",
            cpu_logical_cores=0,
            cpu_physical_cores=1,
            cpu_usage_percent=10.0,
            memory_total_bytes=100,
            memory_used_bytes=50,
            memory_usage_percent=50.0,
            disk_total_bytes=100,
            disk_used_bytes=50,
            disk_usage_percent=50.0,
        )

    with pytest.raises(InvalidHealthMetricError, match="CPU usage percent"):
        _make_hardware(cpu_usage=120.0)


def test_software_metrics_validation_rejects_empty_hostname() -> None:
    """Verify SoftwareMetrics rejects blank hostname or negative uptime."""
    with pytest.raises(InvalidHealthMetricError, match="hostname"):
        _make_software(hostname="   ")


def test_tier_node_health_and_link_validation() -> None:
    """Verify TierNodeHealth and ChainLinkStatus reject invalid status strings."""
    with pytest.raises(InvalidHealthMetricError, match="Invalid tier status"):
        TierNodeHealth(
            tier_id="business",
            tier_label="Business",
            status="invalid_state",
            latency_ms=1.0,
            checked_at_iso="2026-10-17T12:00:00Z",
            hardware=_make_hardware(),
            software=_make_software(),
        )

    with pytest.raises(InvalidHealthMetricError, match="Invalid link status"):
        ChainLinkStatus(
            source_tier="presentation",
            target_tier="business",
            protocol="HTTP",
            status="broken",
            latency_ms=1.0,
            details="link",
        )


def test_health_chain_domain_service_builds_healthy_and_degraded_summaries() -> None:
    """Verify HealthChainDomainService computes overall status, links, and total latency."""
    domain_service = HealthChainDomainService()
    pres = TierNodeHealth(
        tier_id="presentation",
        tier_label="Presentation",
        status="healthy",
        latency_ms=1.5,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("mamtemplate-presentation"),
    )
    biz = TierNodeHealth(
        tier_id="business",
        tier_label="Business",
        status="healthy",
        latency_ms=2.5,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("mamtemplate-business"),
    )
    data_ok = TierNodeHealth(
        tier_id="data",
        tier_label="Data",
        status="healthy",
        latency_ms=3.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("mamtemplate-data"),
    )

    summary_ok = domain_service.build_chain_summary(
        app_name="MAMTemplate",
        environment="production",
        checked_at_iso="2026-10-17T12:00:00Z",
        presentation_tier=pres,
        business_tier=biz,
        data_tier=data_ok,
    )
    assert summary_ok.overall_status == "healthy"
    assert summary_ok.total_latency_ms == 7.0
    assert len(summary_ok.links) == 3
    assert all(link.status == "connected" for link in summary_ok.links)

    data_down = TierNodeHealth(
        tier_id="data",
        tier_label="Data",
        status="unhealthy",
        latency_ms=5.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("mamtemplate-data"),
        error_message="Connection refused",
    )
    summary_degraded = domain_service.build_chain_summary(
        app_name="MAMTemplate",
        environment="production",
        checked_at_iso="2026-10-17T12:00:00Z",
        presentation_tier=pres,
        business_tier=biz,
        data_tier=data_down,
    )
    assert summary_degraded.overall_status == "degraded"
    assert summary_degraded.links[2].status == "disconnected"


def test_health_chain_domain_service_multi_instances_per_tier() -> None:
    """Verify HealthChainDomainService aggregates multiple container instances per tier."""
    domain_service = HealthChainDomainService()
    pres_1 = TierNodeHealth(
        tier_id="presentation",
        tier_label="Presentation #1",
        status="healthy",
        latency_ms=1.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("pres-1"),
    )
    pres_2 = TierNodeHealth(
        tier_id="presentation",
        tier_label="Presentation #2",
        status="healthy",
        latency_ms=3.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("pres-2"),
    )
    biz_1 = TierNodeHealth(
        tier_id="business",
        tier_label="Business #1",
        status="healthy",
        latency_ms=2.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("biz-1"),
    )
    biz_2 = TierNodeHealth(
        tier_id="business",
        tier_label="Business #2",
        status="healthy",
        latency_ms=4.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("biz-2"),
    )
    data_1 = TierNodeHealth(
        tier_id="data",
        tier_label="Data Primary",
        status="healthy",
        latency_ms=5.0,
        checked_at_iso="2026-10-17T12:00:00Z",
        hardware=_make_hardware(),
        software=_make_software("data-1"),
    )

    summary = domain_service.build_chain_summary(
        app_name="MAMTemplate",
        environment="production",
        checked_at_iso="2026-10-17T12:00:00Z",
        presentation_tier=[pres_1, pres_2],
        business_tier=[biz_1, biz_2],
        data_tier=[data_1],
    )
    assert summary.overall_status == "healthy"
    assert len(summary.tiers) == 5
    assert "pres-1, pres-2 (2 instances)" in summary.links[0].details
    assert "biz-1, biz-2 (2 instances)" in summary.links[1].details
