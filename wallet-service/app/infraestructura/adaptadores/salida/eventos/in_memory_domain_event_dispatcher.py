import logging

from app.aplicacion.puertos import DomainEventDispatcher
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

logger = logging.getLogger("wallet.event_bus")


class InMemoryDomainEventDispatcher(DomainEventDispatcher):
    """Bus interno síncrono, reemplazable sin cambiar los casos de uso."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[DomainEventHandler]] = {}

    def suscribir(
        self, tipo_evento: type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        self._handlers.setdefault(tipo_evento, []).append(handler)

    def despachar(self, evento: DomainEvent) -> None:
        handlers = self._handlers_para(type(evento))
        if not handlers:
            logger.warning(
                "evento de dominio sin suscriptores: %s", type(evento).__name__
            )
            return
        for handler in handlers:
            self._ejecutar(handler, evento)

    def _handlers_para(self, tipo: type[DomainEvent]) -> list[DomainEventHandler]:
        """Recorre la jerarquía para incluir suscripciones a las clases base."""

        return [
            handler
            for clase in tipo.__mro__
            for handler in self._handlers.get(clase, ())
        ]

    @staticmethod
    def _ejecutar(handler: DomainEventHandler, evento: DomainEvent) -> None:
        """Aísla el fallo: un suscriptor roto no impide que los demás corran.

        El agregado ya se persistió cuando llegamos aquí, así que propagar el
        error solo produciría una respuesta que contradice el estado guardado.
        """

        try:
            handler.manejar(evento)
        except Exception:
            logger.exception(
                "handler=%s falló procesando %s event_id=%s",
                type(handler).__name__,
                type(evento).__name__,
                evento.event_id,
            )
