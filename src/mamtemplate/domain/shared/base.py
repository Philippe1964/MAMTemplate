"""Shared domain building blocks (base entities, aggregates, events, specifications, exceptions)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import DeclarativeBase


class BaseEntity(DeclarativeBase):
    """Base declarative class for persistent DDD Domain Entities."""


@dataclass(frozen=True, slots=True, kw_only=True)
class DomainEvent:
    """Base class for all immutable DDD Domain Events representing past business facts."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class AggregateRoot:
    """Mixin for DDD Aggregate Roots supporting internal Domain Event recording."""

    def __init__(self) -> None:
        """Initialize the aggregate root's internal transient domain event buffer."""
        self._domain_events: list[DomainEvent] = []

    def _record_event(self, event: DomainEvent) -> None:
        """Record a domain event raised during an aggregate state transition."""
        if not hasattr(self, "_domain_events"):
            self._domain_events = []
        self._domain_events.append(event)

    def pull_domain_events(self) -> list[DomainEvent]:
        """Drain and return all recorded domain events in FIFO order."""
        if not hasattr(self, "_domain_events"):
            return []
        events = list(self._domain_events)
        self._domain_events.clear()
        return events


class Specification[T](ABC):
    """Composable DDD Specification for encapsulating and combining business predicates."""

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True when the candidate domain object satisfies this business rule."""

    def __and__(self, other: Specification[T]) -> Specification[T]:
        """Combine two specifications with logical AND."""
        return _AndSpecification(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        """Combine two specifications with logical OR."""
        return _OrSpecification(self, other)

    def __invert__(self) -> Specification[T]:
        """Negate this specification with logical NOT."""
        return _NotSpecification(self)


class _AndSpecification[T](Specification[T]):
    """Composite specification requiring both left and right specifications to be satisfied."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True if both specifications are satisfied."""
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class _OrSpecification[T](Specification[T]):
    """Composite specification requiring either left or right specification to be satisfied."""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True if either specification is satisfied."""
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class _NotSpecification[T](Specification[T]):
    """Composite specification negating the wrapped specification."""

    def __init__(self, wrapped: Specification[T]) -> None:
        self._wrapped = wrapped

    def is_satisfied_by(self, candidate: T) -> bool:
        """Return True if the wrapped specification is not satisfied."""
        return not self._wrapped.is_satisfied_by(candidate)


class DomainError(Exception):
    """Base exception for all business rule violations in the Domain layer."""


class EntityNotFoundError(DomainError):
    """Raised when a requested domain entity cannot be found."""


__all__ = [
    "AggregateRoot",
    "BaseEntity",
    "DomainError",
    "DomainEvent",
    "EntityNotFoundError",
    "Specification",
]
