from typing import Protocol

from dominio.seedwork import DomainEvent


class DomainEventDispatcher(Protocol):
    """Puerto para entregar eventos de dominio a manejadores internos."""

    def despachar(self, evento: DomainEvent) -> None: ...
