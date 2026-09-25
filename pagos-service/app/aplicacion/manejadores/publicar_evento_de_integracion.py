import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

from .traductores import TRADUCTORES, Traductor

logger = logging.getLogger("pagos.integration_events")


class PublicarEventoDeIntegracionHandler(DomainEventHandler[DomainEvent]):
    """Traduce un evento de dominio y lo publica hacia otros bounded contexts.

    No se traduce `PagoCreado`: es un hecho puramente interno de PagosBC, a
    nadie más le interesa que un pago exista antes de que se resuelva.
    Recibe el puerto `MessageBroker`: no sabe si detrás hay Pulsar o logs.
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
            return
        for traducir in traductores:
            self._broker.publicar(traducir(evento))
