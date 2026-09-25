"""Bloques genéricos de la capa de aplicación."""

from .domain_event_handler import DomainEventHandler
from .integration_event import IntegrationEvent

__all__ = ["DomainEventHandler", "IntegrationEvent"]
