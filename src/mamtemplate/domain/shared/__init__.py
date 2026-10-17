"""Shared domain components sub-package."""

from mamtemplate.domain.shared.base import BaseEntity, DomainError, EntityNotFoundError

__all__ = ["BaseEntity", "DomainError", "EntityNotFoundError"]
