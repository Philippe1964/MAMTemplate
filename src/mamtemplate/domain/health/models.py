"""Domain value objects representing hardware/software metrics and multi-instance tier health."""

from dataclasses import dataclass

from mamtemplate.domain.shared.base import DomainError


class InvalidHealthMetricError(DomainError):
    """Raised when a hardware, software, or health metric violates domain invariants."""


@dataclass(frozen=True, slots=True)
class HardwareMetrics:
    """Immutable value object encapsulating hardware resource metrics of a tier container."""

    cpu_model: str
    cpu_logical_cores: int
    cpu_physical_cores: int
    cpu_usage_percent: float
    memory_total_bytes: int
    memory_used_bytes: int
    memory_usage_percent: float
    disk_total_bytes: int
    disk_used_bytes: int
    disk_usage_percent: float

    def __post_init__(self) -> None:
        """Validate hardware metric invariants at construction time.

        Raises:
            InvalidHealthMetricError: If any hardware metric is out of valid bounds.
        """
        if self.cpu_logical_cores < 1 or self.cpu_physical_cores < 1:
            msg = "CPU core counts must be at least 1."
            raise InvalidHealthMetricError(msg)
        if not (0.0 <= self.cpu_usage_percent <= 100.0):
            msg = f"CPU usage percent must be between 0 and 100, got {self.cpu_usage_percent}."
            raise InvalidHealthMetricError(msg)
        if self.memory_total_bytes < 0 or self.memory_used_bytes < 0:
            msg = "Memory byte values must be non-negative."
            raise InvalidHealthMetricError(msg)
        if not (0.0 <= self.memory_usage_percent <= 100.0):
            msg = (
                f"Memory usage percent must be between 0 and 100, got {self.memory_usage_percent}."
            )
            raise InvalidHealthMetricError(msg)
        if self.disk_total_bytes < 0 or self.disk_used_bytes < 0:
            msg = "Disk byte values must be non-negative."
            raise InvalidHealthMetricError(msg)
        if not (0.0 <= self.disk_usage_percent <= 100.0):
            msg = f"Disk usage percent must be between 0 and 100, got {self.disk_usage_percent}."
            raise InvalidHealthMetricError(msg)


@dataclass(frozen=True, slots=True)
class SoftwareMetrics:
    """Immutable value object encapsulating software and OS characteristics of a container."""

    hostname: str
    os_name: str
    os_release: str
    architecture: str
    service_name: str
    service_version: str
    uptime_seconds: float
    details: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Validate software metric invariants at construction time.

        Raises:
            InvalidHealthMetricError: If hostname, service_name, or uptime is invalid.
        """
        if not self.hostname.strip():
            msg = "SoftwareMetrics.hostname must not be empty."
            raise InvalidHealthMetricError(msg)
        if not self.service_name.strip():
            msg = "SoftwareMetrics.service_name must not be empty."
            raise InvalidHealthMetricError(msg)
        if self.uptime_seconds < 0.0:
            msg = "SoftwareMetrics.uptime_seconds must be non-negative."
            raise InvalidHealthMetricError(msg)


@dataclass(frozen=True, slots=True)
class TierNodeHealth:
    """Immutable value object representing the operational state of one container instance."""

    tier_id: str
    tier_label: str
    status: str
    latency_ms: float
    checked_at_iso: str
    hardware: HardwareMetrics
    software: SoftwareMetrics
    error_message: str | None = None
    instance_id: str = ""

    def __post_init__(self) -> None:
        """Validate tier health invariants and default instance_id to hostname if empty.

        Raises:
            InvalidHealthMetricError: If status or latency is invalid.
        """
        if self.status not in {"healthy", "degraded", "unhealthy"}:
            msg = f"Invalid tier status '{self.status}'."
            raise InvalidHealthMetricError(msg)
        if self.latency_ms < 0.0:
            msg = "Latency in milliseconds must be non-negative."
            raise InvalidHealthMetricError(msg)
        if not self.instance_id:
            object.__setattr__(self, "instance_id", self.software.hostname)


@dataclass(frozen=True, slots=True)
class ChainLinkStatus:
    """Immutable value object describing the network/protocol link between two adjacent tiers."""

    source_tier: str
    target_tier: str
    protocol: str
    status: str
    latency_ms: float
    details: str

    def __post_init__(self) -> None:
        """Validate link status invariants at construction time.

        Raises:
            InvalidHealthMetricError: If link status or latency is invalid.
        """
        if self.status not in {"connected", "degraded", "disconnected"}:
            msg = f"Invalid link status '{self.status}'."
            raise InvalidHealthMetricError(msg)
        if self.latency_ms < 0.0:
            msg = "Link latency must be non-negative."
            raise InvalidHealthMetricError(msg)


@dataclass(frozen=True, slots=True)
class ChainHealthSummary:
    """Immutable aggregate value object representing the complete multi-instance 3-tier report."""

    overall_status: str
    app_name: str
    environment: str
    checked_at_iso: str
    total_latency_ms: float
    tiers: tuple[TierNodeHealth, ...]
    links: tuple[ChainLinkStatus, ...]


__all__ = [
    "ChainHealthSummary",
    "ChainLinkStatus",
    "HardwareMetrics",
    "InvalidHealthMetricError",
    "SoftwareMetrics",
    "TierNodeHealth",
]
