"""Bloques genéricos de la capa de aplicación."""

from .application_error import ApplicationError
from .domain_event_handler import DomainEventHandler
from .integration_event import IntegrationEvent

__all__ = ["ApplicationError", "DomainEventHandler", "IntegrationEvent"]
