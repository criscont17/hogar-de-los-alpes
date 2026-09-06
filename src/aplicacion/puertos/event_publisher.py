from typing import Protocol

from dominio.seedwork import DomainEvent


class EventPublisher(Protocol):
    """Puerto de salida para publicar eventos de integración hacia otros BC."""

    def publicar(self, evento: DomainEvent) -> None: ...
