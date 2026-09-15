"""Bloques genéricos de la capa de aplicación."""

from .application_error import ApplicationError
from .domain_event_handler import DomainEventHandler

__all__ = ["ApplicationError", "DomainEventHandler"]
