"""Domain repository protocol for probing single or multiple container instances per tier."""

from typing import Protocol

from mamtemplate.domain.health.models import TierNodeHealth


class HealthCheckRepository(Protocol):
    """Repository interface for collecting hardware/software metrics across all tier instances."""

    async def probe_presentation_tier(
        self,
        forwarded_headers: dict[str, str] | None = None,
    ) -> TierNodeHealth:
        """Probe the primary Presentation tier instance.

        Args:
            forwarded_headers: Optional HTTP headers forwarded by the presentation proxy.

        Returns:
            The TierNodeHealth for a Presentation tier instance.
        """
        ...

    async def probe_business_tier(self) -> TierNodeHealth:
        """Probe the current Business tier instance.

        Returns:
            The TierNodeHealth for the current Business tier instance.
        """
        ...

    async def probe_data_tier(self) -> TierNodeHealth:
        """Probe the primary Data tier instance.

        Returns:
            The TierNodeHealth for a Data tier instance.
        """
        ...

    async def probe_all_presentation_instances(
        self,
        forwarded_headers: dict[str, str] | None = None,
    ) -> list[TierNodeHealth]:
        """Discover and probe all running container instances of the Presentation tier.

        Args:
            forwarded_headers: Optional HTTP headers forwarded by the presentation proxy.

        Returns:
            List of TierNodeHealth for every discovered Presentation container instance.
        """
        ...

    async def probe_all_business_instances(self) -> list[TierNodeHealth]:
        """Discover and probe all running container instances of the Business tier.

        Returns:
            List of TierNodeHealth for every discovered Business container instance.
        """
        ...

    async def probe_all_data_instances(self) -> list[TierNodeHealth]:
        """Discover and probe all running container instances of the Data tier.

        Returns:
            List of TierNodeHealth for every discovered Data container instance.
        """
        ...
