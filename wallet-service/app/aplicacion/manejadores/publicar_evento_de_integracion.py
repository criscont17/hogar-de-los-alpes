import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

from .traductores import TRADUCTORES, Traductor

logger = logging.getLogger("wallet.integration_events")


class PublicarEventoDeIntegracionHandler(DomainEventHandler[DomainEvent]):
    """Traduce un evento de dominio y lo publica hacia otros bounded contexts.

    Recibe el puerto `MessageBroker` por constructor, así que no sabe si detrás
    hay RabbitMQ, SQS o un adaptador de logs: cambiar de plataforma de mensajería
    no toca esta clase.
    """

    def __init__(
        self,
        broker: MessageBroker,
        traductores: dict[type[DomainEvent], Traductor] | None = None,
    ) -> None:
        self._broker = broker
        self._traductores = TRADUCTORES if traductores is None else traductores

    def manejar(self, evento: DomainEvent) -> None:
        traductor = self._traductores.get(type(evento))
        if traductor is None:
            logger.warning(
                "evento de dominio sin traductor de integración: %s",
                type(evento).__name__,
            )
            return
        self._broker.publicar(traductor(evento))
