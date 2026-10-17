"""Unit tests for shared domain building blocks."""

from dataclasses import dataclass

from mamtemplate.domain.shared.base import (
    AggregateRoot,
    BaseEntity,
    DomainError,
    DomainEvent,
    EntityNotFoundError,
    Specification,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class _SampleRecordedEvent(DomainEvent):
    """Sample concrete domain event for testing AggregateRoot event recording."""

    aggregate_name: str


class _SampleAggregate(AggregateRoot):
    """Sample aggregate root recording domain events on state change."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    def rename(self, new_name: str) -> None:
        """Change aggregate name and record a domain event."""
        self._name = new_name
        self._record_event(_SampleRecordedEvent(aggregate_name=new_name))


class _PositiveIntSpec(Specification[int]):
    """Specification satisfied by strictly positive integers."""

    def is_satisfied_by(self, candidate: int) -> bool:
        """Return True when candidate > 0."""
        return candidate > 0


class _EvenIntSpec(Specification[int]):
    """Specification satisfied by even integers."""

    def is_satisfied_by(self, candidate: int) -> bool:
        """Return True when candidate is divisible by 2."""
        return candidate % 2 == 0


def test_domain_exceptions_hierarchy() -> None:
    """Verify that EntityNotFoundError inherits from DomainError."""
    err = EntityNotFoundError("Client 42 not found")
    assert isinstance(err, DomainError)
    assert str(err) == "Client 42 not found"


def test_base_entity_metadata_exists() -> None:
    """Verify that BaseEntity exposes a SQLAlchemy MetaData registry."""
    assert BaseEntity.metadata is not None


def test_aggregate_root_records_and_pulls_domain_events() -> None:
    """Verify AggregateRoot records domain events in FIFO order and clears buffer on pull."""
    aggregate = _SampleAggregate("initial")
    assert aggregate.pull_domain_events() == []

    aggregate.rename("updated-1")
    aggregate.rename("updated-2")

    events = aggregate.pull_domain_events()
    assert len(events) == 2
    assert isinstance(events[0], _SampleRecordedEvent)
    assert events[0].aggregate_name == "updated-1"
    assert events[0].occurred_at.tzinfo is not None
    assert isinstance(events[1], _SampleRecordedEvent)
    assert events[1].aggregate_name == "updated-2"
    assert aggregate.pull_domain_events() == []


def test_aggregate_root_without_super_init_handles_events_gracefully() -> None:
    """Verify AggregateRoot lazily initializes event buffer when ORM bypasses __init__."""
    aggregate = object.__new__(_SampleAggregate)
    assert aggregate.pull_domain_events() == []
    aggregate.rename("orm-hydrated")
    pulled = aggregate.pull_domain_events()
    assert len(pulled) == 1


def test_specification_boolean_composition() -> None:
    """Verify Specification supports AND (&), OR (|), and NOT (~) composition."""
    positive = _PositiveIntSpec()
    even = _EvenIntSpec()

    positive_and_even = positive & even
    assert positive_and_even.is_satisfied_by(4) is True
    assert positive_and_even.is_satisfied_by(3) is False
    assert positive_and_even.is_satisfied_by(-2) is False

    positive_or_even = positive | even
    assert positive_or_even.is_satisfied_by(3) is True
    assert positive_or_even.is_satisfied_by(-2) is True
    assert positive_or_even.is_satisfied_by(-3) is False

    not_positive = ~positive
    assert not_positive.is_satisfied_by(-1) is True
    assert not_positive.is_satisfied_by(5) is False
