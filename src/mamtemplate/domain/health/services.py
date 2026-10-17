"""Domain service evaluating the end-to-end 3-tier chain health across 1..N container instances."""

from collections.abc import Sequence

from mamtemplate.domain.health.models import (
    ChainHealthSummary,
    ChainLinkStatus,
    TierNodeHealth,
)


def _aggregate_group_status(nodes: Sequence[TierNodeHealth]) -> str:
    """Compute the aggregated health status of a group of container instances for one tier.

    Args:
        nodes: Non-empty sequence of container health nodes for the tier.

    Returns:
        'healthy' if all instances are healthy, 'unhealthy' if all are unhealthy, else 'degraded'.
    """
    if not nodes:
        return "unhealthy"
    statuses = {n.status for n in nodes}
    if statuses == {"healthy"}:
        return "healthy"
    if statuses == {"unhealthy"}:
        return "unhealthy"
    return "degraded"


def _average_latency(nodes: Sequence[TierNodeHealth]) -> float:
    """Compute the average latency across a tier's instances.

    Args:
        nodes: Sequence of container health nodes.

    Returns:
        Average latency in milliseconds rounded to 2 decimal places.
    """
    if not nodes:
        return 0.0
    return round(sum(n.latency_ms for n in nodes) / len(nodes), 2)


def _format_tier_hosts(nodes: Sequence[TierNodeHealth]) -> str:
    """Format the list of container hostnames for a tier.

    Args:
        nodes: Sequence of container health nodes.

    Returns:
        Summary string of hostnames and instance count.
    """
    hosts = [n.software.hostname for n in nodes]
    if len(hosts) == 1:
        return hosts[0]
    return f"{', '.join(hosts)} ({len(hosts)} instances)"


class HealthChainDomainService:
    """Domain service that evaluates the health of the full Presentation-Business-Data chain."""

    def build_chain_summary(
        self,
        *,
        app_name: str,
        environment: str,
        checked_at_iso: str,
        presentation_tier: TierNodeHealth | Sequence[TierNodeHealth],
        business_tier: TierNodeHealth | Sequence[TierNodeHealth],
        data_tier: TierNodeHealth | Sequence[TierNodeHealth],
    ) -> ChainHealthSummary:
        """Evaluate single or multi-instance tier statuses and construct the 3-tier summary.

        Args:
            app_name: Name of the application.
            environment: Deployment environment name.
            checked_at_iso: ISO-8601 UTC timestamp of the check.
            presentation_tier: Single or sequence of Presentation tier instances.
            business_tier: Single or sequence of Business tier instances.
            data_tier: Single or sequence of Data tier instances.

        Returns:
            A validated ChainHealthSummary value object containing all container instances.
        """
        pres_nodes: tuple[TierNodeHealth, ...] = (
            (presentation_tier,)
            if isinstance(presentation_tier, TierNodeHealth)
            else tuple(presentation_tier)
        )
        biz_nodes: tuple[TierNodeHealth, ...] = (
            (business_tier,) if isinstance(business_tier, TierNodeHealth) else tuple(business_tier)
        )
        data_nodes: tuple[TierNodeHealth, ...] = (
            (data_tier,) if isinstance(data_tier, TierNodeHealth) else tuple(data_tier)
        )

        all_tiers = (*pres_nodes, *biz_nodes, *data_nodes)
        pres_status = _aggregate_group_status(pres_nodes)
        biz_status = _aggregate_group_status(biz_nodes)
        data_status = _aggregate_group_status(data_nodes)

        tier_statuses = {pres_status, biz_status, data_status}
        if tier_statuses == {"healthy"}:
            overall_status = "healthy"
        elif biz_status == "unhealthy":
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        pres_to_biz_status = (
            "connected"
            if pres_status == "healthy" and biz_status == "healthy"
            else ("disconnected" if "unhealthy" in {pres_status, biz_status} else "degraded")
        )
        biz_to_data_status = (
            "connected"
            if biz_status == "healthy" and data_status == "healthy"
            else ("disconnected" if "unhealthy" in {biz_status, data_status} else "degraded")
        )

        pres_lat = _average_latency(pres_nodes)
        biz_lat = _average_latency(biz_nodes)
        data_lat = _average_latency(data_nodes)

        pres_hosts = _format_tier_hosts(pres_nodes)
        biz_hosts = _format_tier_hosts(biz_nodes)
        data_hosts = _format_tier_hosts(data_nodes)

        links = (
            ChainLinkStatus(
                source_tier="browser",
                target_tier="presentation",
                protocol="HTTP/1.1 (Port 8080 -> 80)",
                status="connected" if pres_status != "unhealthy" else "degraded",
                latency_ms=pres_lat,
                details=f"Reverse Proxy Gateway ({pres_hosts})",
            ),
            ChainLinkStatus(
                source_tier="presentation",
                target_tier="business",
                protocol="HTTP/1.1 Load-Balanced (presentation_net :8000)",
                status=pres_to_biz_status,
                latency_ms=round(pres_lat + biz_lat, 2),
                details=f"{pres_hosts} -> {biz_hosts}",
            ),
            ChainLinkStatus(
                source_tier="business",
                target_tier="data",
                protocol="TCP/PostgreSQL Wire Protocol (data_net :5432)",
                status=biz_to_data_status,
                latency_ms=data_lat,
                details=f"{biz_hosts} -> {data_hosts}",
            ),
        )

        total_latency_ms = round(pres_lat + biz_lat + data_lat, 2)

        return ChainHealthSummary(
            overall_status=overall_status,
            app_name=app_name,
            environment=environment,
            checked_at_iso=checked_at_iso,
            total_latency_ms=total_latency_ms,
            tiers=all_tiers,
            links=links,
        )
