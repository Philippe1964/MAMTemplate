"""FastAPI routers for Cloud-Native probes and multi-instance 3-tier diagnostics."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mamtemplate.application.health.health_service import (
    CheckBusinessInstanceRequestDto,
    CheckBusinessInstanceResponseDto,
    CheckChainHealthRequestDto,
    CheckChainHealthResponseDto,
    CheckHealthRequestDto,
    CheckHealthResponseDto,
    HealthApplicationService,
)
from mamtemplate.domain.health.services import HealthChainDomainService
from mamtemplate.domain.shared.base import DomainError
from mamtemplate.infrastructure.config.settings import AppSettings, get_settings
from mamtemplate.infrastructure.monitoring.health.health_check_repository_impl import (
    HealthCheckRepositoryImpl,
)
from mamtemplate.infrastructure.persistence.session import get_async_session

router = APIRouter(tags=["health"])


def get_health_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
) -> HealthApplicationService:
    """Provide the lightweight HealthApplicationService via FastAPI dependency injection.

    Args:
        settings: Injected application settings.

    Returns:
        Configured HealthApplicationService instance.
    """
    return HealthApplicationService(
        app_name=settings.app_name,
        environment=settings.environment,
    )


def get_chain_health_service(
    settings: Annotated[AppSettings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_async_session)],
) -> HealthApplicationService:
    """Provide the 3-tier HealthApplicationService wired with HealthCheckRepositoryImpl.

    Args:
        settings: Injected application settings.
        session: Injected SQLAlchemy AsyncSession.

    Returns:
        Configured HealthApplicationService instance with repository and domain service.
    """
    repository = HealthCheckRepositoryImpl(
        session=session,
        presentation_metrics_url=settings.presentation_metrics_url,
        business_service_host=settings.business_service_host,
        business_service_port=settings.business_service_port,
    )
    return HealthApplicationService(
        app_name=settings.app_name,
        environment=settings.environment,
        repository=repository,
        domain_service=HealthChainDomainService(),
    )


@router.get(
    "/health",
    response_model=CheckHealthResponseDto,
    status_code=status.HTTP_200_OK,
)
@router.get(
    "/health/live",
    response_model=CheckHealthResponseDto,
    status_code=status.HTTP_200_OK,
)
async def check_health_endpoint(
    service: Annotated[HealthApplicationService, Depends(get_health_service)],
) -> CheckHealthResponseDto:
    """Return the lightweight liveness health status of the Business replica.

    Args:
        service: Injected HealthApplicationService.

    Returns:
        The CheckHealthResponseDto payload.

    Raises:
        HTTPException: If a domain or application error occurs.
    """
    try:
        return await service.check_health(CheckHealthRequestDto())
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/health/ready",
    response_model=CheckHealthResponseDto,
    status_code=status.HTTP_200_OK,
)
async def check_readiness_endpoint(
    request: Request,
    service: Annotated[HealthApplicationService, Depends(get_chain_health_service)],
) -> CheckHealthResponseDto:
    """Return Cloud-Native readiness status (verifying database connectivity).

    Args:
        request: Incoming FastAPI HTTP request.
        service: Injected 3-tier HealthApplicationService.

    Returns:
        The CheckHealthResponseDto when the replica and database connection are ready.

    Raises:
        HTTPException: HTTP 503 if the Data tier is unreachable, or 400 on domain error.
    """
    try:
        forwarded_headers = {str(k): str(v) for k, v in request.headers.items()}
        chain = await service.check_chain_health(
            CheckChainHealthRequestDto(forwarded_headers=forwarded_headers)
        )
        data_tiers = [t for t in chain.tiers if t.tier_id == "data"]
        if data_tiers and all(t.status == "unhealthy" for t in data_tiers):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=data_tiers[0].error_message or "Data tier is not ready.",
            )
        return CheckHealthResponseDto(
            status="ready",
            app_name=chain.app_name,
            environment=chain.environment,
        )
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/internal/business-metrics",
    response_model=CheckBusinessInstanceResponseDto,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def check_business_instance_endpoint(
    service: Annotated[HealthApplicationService, Depends(get_chain_health_service)],
) -> CheckBusinessInstanceResponseDto:
    """Return hardware and software telemetry for this specific Business container replica.

    Args:
        service: Injected HealthApplicationService.

    Returns:
        The local Business replica telemetry DTO.
    """
    try:
        return await service.check_business_instance(CheckBusinessInstanceRequestDto())
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/health-check",
    response_model=CheckChainHealthResponseDto,
    status_code=status.HTTP_200_OK,
)
async def check_chain_health_endpoint(
    request: Request,
    service: Annotated[HealthApplicationService, Depends(get_chain_health_service)],
) -> CheckChainHealthResponseDto:
    """Return the complete multi-instance 3-tier hardware/software health diagnostic report.

    Args:
        request: Incoming FastAPI HTTP request (used to inspect proxy headers).
        service: Injected HealthApplicationService.

    Returns:
        The CheckChainHealthResponseDto payload.

    Raises:
        HTTPException: If a domain or application error occurs.
    """
    try:
        forwarded_headers = {str(k): str(v) for k, v in request.headers.items()}
        dto = CheckChainHealthRequestDto(forwarded_headers=forwarded_headers)
        return await service.check_chain_health(dto)
    except DomainError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
