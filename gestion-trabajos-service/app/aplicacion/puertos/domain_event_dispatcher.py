from abc import ABC, abstractmethod

from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent


class DomainEventDispatcher(ABC):
    """Puerto del bus interno de eventos de dominio.

    Los casos de uso solo despachan; qué ocurre después lo deciden los handlers
    suscritos. Suscribirse a una clase base entrega también sus subtipos.
    """

    @abstractmethod
    def suscribir(
        self, tipo_evento: type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        """Registra un handler para un tipo de evento y sus descendientes."""

    @abstractmethod
    def despachar(self, evento: DomainEvent) -> None:
        """Entrega el evento a todos los handlers suscritos."""
