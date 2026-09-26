"""Bloques genéricos de la capa de aplicación."""

from .domain_event_handler import DomainEventHandler
from .integration_event import IntegrationEvent
from .sobre_de_evento import SobreDeEvento

__all__ = ["DomainEventHandler", "IntegrationEvent", "SobreDeEvento"]
