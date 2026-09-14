import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

from .traductores import TRADUCTORES, Traductor

logger = logging.getLogger("trabajos.integration_events")


class PublicarEventoDeIntegracionHandler(DomainEventHandler[DomainEvent]):
    """Traduce un evento de dominio y lo publica hacia otros bounded contexts.

    Un mismo hecho puede salir en varias versiones del contrato a la vez (por
    ejemplo `TrabajoCreadoV1` y `TrabajoCreadoV2`) mientras los consumidores
    migran. Recibe el puerto `MessageBroker`: no sabe si detrás hay Pulsar o logs.
    """

    def __init__(
        self,
        broker: MessageBroker,
        traductores: dict[type[DomainEvent], tuple[Traductor, ...]] | None = None,
    ) -> None:
        self._broker = broker
        self._traductores = TRADUCTORES if traductores is None else traductores

    def manejar(self, evento: DomainEvent) -> None:
        traductores = self._traductores.get(type(evento))
        if not traductores:
            logger.warning(
                "evento de dominio sin traductor de integración: %s",
                type(evento).__name__,
            )
            return
        for traducir in traductores:
            self._broker.publicar(traducir(evento))
