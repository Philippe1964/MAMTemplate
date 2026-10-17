"""System and multi-instance 3-tier chain health check use cases, DTOs, and mappers."""

import datetime
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from mamtemplate.domain.health.models import (
    ChainHealthSummary,
    ChainLinkStatus,
    HardwareMetrics,
    SoftwareMetrics,
    TierNodeHealth,
)
from mamtemplate.domain.health.repositories import HealthCheckRepository
from mamtemplate.domain.health.services import HealthChainDomainService
from mamtemplate.domain.shared.base import DomainError


class ApplicationConfigurationError(DomainError):
    """Raised when an application use case is invoked without its required dependencies."""


class CheckHealthRequestDto(BaseModel):
    """Input DTO for the lightweight check_health use case."""

    model_config = ConfigDict(frozen=True)


class CheckHealthResponseDto(BaseModel):
    """Output DTO for the lightweight check_health use case."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    status: str
    app_name: str
    environment: str


class CheckChainHealthRequestDto(BaseModel):
    """Input DTO for the check_chain_health 3-tier diagnostic use case."""

    model_config = ConfigDict(frozen=True)

    forwarded_headers: dict[str, str] = Field(default_factory=dict)


class CheckBusinessInstanceRequestDto(BaseModel):
    """Input DTO for probing the local Business container instance metrics."""

    model_config = ConfigDict(frozen=True)


class HardwareMetricsDto(BaseModel):
    """DTO representing hardware metrics for a single container instance."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

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


class SoftwareMetricsDto(BaseModel):
    """DTO representing software and OS characteristics for a single container instance."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    hostname: str
    os_name: str
    os_release: str
    architecture: str
    service_name: str
    service_version: str
    uptime_seconds: float
    details: dict[str, str]


class TierNodeHealthDto(BaseModel):
    """DTO representing the health and hardware/software telemetry of a container instance."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    tier_id: str
    tier_label: str
    instance_id: str = ""
    status: str
    latency_ms: float
    checked_at_iso: str
    hardware: HardwareMetricsDto
    software: SoftwareMetricsDto
    error_message: str | None = None


class CheckBusinessInstanceResponseDto(TierNodeHealthDto):
    """Output DTO for the check_business_instance use case."""


class ChainLinkStatusDto(BaseModel):
    """DTO representing the network/protocol link status between two adjacent tiers."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    source_tier: str
    target_tier: str
    protocol: str
    status: str
    latency_ms: float
    details: str


class CheckChainHealthResponseDto(BaseModel):
    """Output DTO for the check_chain_health use case across all container instances."""

    model_config = ConfigDict(from_attributes=True, frozen=True)

    overall_status: str
    app_name: str
    environment: str
    checked_at_iso: str
    total_latency_ms: float
    tiers: list[TierNodeHealthDto]
    links: list[ChainLinkStatusDto]


class HealthDtoMapper:
    """Dedicated mapper transforming Domain health value objects into Application DTOs."""

    @staticmethod
    def to_hardware_dto(hardware: HardwareMetrics) -> HardwareMetricsDto:
        """Transform a HardwareMetrics domain value object into a HardwareMetricsDto.

        Args:
            hardware: Domain hardware metrics.

        Returns:
            Corresponding HardwareMetricsDto.
        """
        return HardwareMetricsDto.model_validate(hardware)

    @staticmethod
    def to_software_dto(software: SoftwareMetrics) -> SoftwareMetricsDto:
        """Transform a SoftwareMetrics domain value object into a SoftwareMetricsDto.

        Args:
            software: Domain software metrics.

        Returns:
            Corresponding SoftwareMetricsDto.
        """
        return SoftwareMetricsDto(
            hostname=software.hostname,
            os_name=software.os_name,
            os_release=software.os_release,
            architecture=software.architecture,
            service_name=software.service_name,
            service_version=software.service_version,
            uptime_seconds=software.uptime_seconds,
            details=dict(software.details),
        )

    @classmethod
    def to_tier_dto(cls, tier: TierNodeHealth) -> TierNodeHealthDto:
        """Transform a TierNodeHealth domain value object into a TierNodeHealthDto.

        Args:
            tier: Domain tier node health object.

        Returns:
            Corresponding TierNodeHealthDto.
        """
        return TierNodeHealthDto(
            tier_id=tier.tier_id,
            tier_label=tier.tier_label,
            instance_id=tier.instance_id or tier.software.hostname,
            status=tier.status,
            latency_ms=tier.latency_ms,
            checked_at_iso=tier.checked_at_iso,
            hardware=cls.to_hardware_dto(tier.hardware),
            software=cls.to_software_dto(tier.software),
            error_message=tier.error_message,
        )

    @staticmethod
    def to_link_dto(link: ChainLinkStatus) -> ChainLinkStatusDto:
        """Transform a ChainLinkStatus domain value object into a ChainLinkStatusDto.

        Args:
            link: Domain chain link status object.

        Returns:
            Corresponding ChainLinkStatusDto.
        """
        return ChainLinkStatusDto.model_validate(link)

    @classmethod
    def to_response_dto(cls, summary: ChainHealthSummary) -> CheckChainHealthResponseDto:
        """Transform a ChainHealthSummary domain object into a CheckChainHealthResponseDto.

        Args:
            summary: Complete domain chain health summary.

        Returns:
            Corresponding CheckChainHealthResponseDto.
        """
        return CheckChainHealthResponseDto(
            overall_status=summary.overall_status,
            app_name=summary.app_name,
            environment=summary.environment,
            checked_at_iso=summary.checked_at_iso,
            total_latency_ms=summary.total_latency_ms,
            tiers=[cls.to_tier_dto(tier) for tier in summary.tiers],
            links=[cls.to_link_dto(link) for link in summary.links],
        )


class HealthApplicationService:
    """Application service orchestrating lightweight and multi-instance 3-tier health use cases."""

    def __init__(
        self,
        app_name: str,
        environment: str,
        repository: HealthCheckRepository | None = None,
        domain_service: HealthChainDomainService | None = None,
    ) -> None:
        """Initialize the service with externalized application metadata and domain collaborators.

        Args:
            app_name: Name of the application.
            environment: Current deployment environment.
            repository: Optional HealthCheckRepository implementation for 3-tier probing.
            domain_service: Optional HealthChainDomainService instance.
        """
        self._app_name = app_name
        self._environment = environment
        self._repository = repository
        self._domain_service = domain_service or HealthChainDomainService()

    async def check_health(
        self,
        request: CheckHealthRequestDto,
    ) -> CheckHealthResponseDto:
        """Execute the lightweight health check use case.

        Args:
            request: The health check request DTO.

        Returns:
            The health status response DTO.
        """
        return CheckHealthResponseDto(
            status="ok",
            app_name=self._app_name,
            environment=self._environment,
        )

    async def check_business_instance(
        self,
        request: CheckBusinessInstanceRequestDto,
    ) -> CheckBusinessInstanceResponseDto:
        """Return the hardware/software telemetry of the local Business container replica.

        Args:
            request: The business instance request DTO.

        Returns:
            The local Business replica's CheckBusinessInstanceResponseDto.

        Raises:
            ApplicationConfigurationError: If no HealthCheckRepository was injected.
        """
        if self._repository is None:
            msg = "HealthCheckRepository is required to execute check_business_instance."
            raise ApplicationConfigurationError(msg)
        node = await self._repository.probe_business_tier()
        tier_dto = HealthDtoMapper.to_tier_dto(node)
        return CheckBusinessInstanceResponseDto.model_validate(tier_dto.model_dump())

    async def check_chain_health(
        self,
        request: CheckChainHealthRequestDto,
    ) -> CheckChainHealthResponseDto:
        """Execute the end-to-end 3-tier chain health check across all container instances.

        Args:
            request: The chain health check request DTO.

        Returns:
            The full 3-tier CheckChainHealthResponseDto.

        Raises:
            ApplicationConfigurationError: If no HealthCheckRepository was injected.
        """
        if self._repository is None:
            msg = "HealthCheckRepository is required to execute check_chain_health."
            raise ApplicationConfigurationError(msg)

        repo = self._repository
        pres_instances = await self._probe_tier_group(
            multi_call=lambda: repo.probe_all_presentation_instances(
                forwarded_headers=request.forwarded_headers,
            ),
            single_call=lambda: repo.probe_presentation_tier(
                forwarded_headers=request.forwarded_headers,
            ),
        )
        biz_instances = await self._probe_tier_group(
            multi_call=repo.probe_all_business_instances,
            single_call=repo.probe_business_tier,
        )
        data_instances = await self._probe_tier_group(
            multi_call=repo.probe_all_data_instances,
            single_call=repo.probe_data_tier,
        )

        checked_at_iso = datetime.datetime.now(datetime.UTC).isoformat()
        summary: ChainHealthSummary = self._domain_service.build_chain_summary(
            app_name=self._app_name,
            environment=self._environment,
            checked_at_iso=checked_at_iso,
            presentation_tier=pres_instances,
            business_tier=biz_instances,
            data_tier=data_instances,
        )
        return HealthDtoMapper.to_response_dto(summary)

    @staticmethod
    async def _probe_tier_group(
        multi_call: Callable[[], Awaitable[list[TierNodeHealth]]],
        single_call: Callable[[], Awaitable[TierNodeHealth]],
    ) -> list[TierNodeHealth]:
        """Execute multi-instance probe if it returns a non-empty list, else fallback to single."""
        result = await multi_call()
        if result:
            return result
        single = await single_call()
        return [single]


__all__ = [
    "ApplicationConfigurationError",
    "ChainLinkStatusDto",
    "CheckBusinessInstanceRequestDto",
    "CheckBusinessInstanceResponseDto",
    "CheckChainHealthRequestDto",
    "CheckChainHealthResponseDto",
    "CheckHealthRequestDto",
    "CheckHealthResponseDto",
    "HardwareMetricsDto",
    "HealthApplicationService",
    "HealthDtoMapper",
    "SoftwareMetricsDto",
    "TierNodeHealthDto",
]


__all__ = [
    "ApplicationConfigurationError",
    "ChainLinkStatusDto",
    "CheckBusinessInstanceRequestDto",
    "CheckBusinessInstanceResponseDto",
    "CheckChainHealthRequestDto",
    "CheckChainHealthResponseDto",
    "CheckHealthRequestDto",
    "CheckHealthResponseDto",
    "HardwareMetricsDto",
    "HealthApplicationService",
    "HealthDtoMapper",
    "SoftwareMetricsDto",
    "TierNodeHealthDto",
]
