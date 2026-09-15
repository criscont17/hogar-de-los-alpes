import logging

from app.aplicacion.puertos import DomainEventDispatcher
from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

logger = logging.getLogger("operaciones.event_bus")


class InMemoryDomainEventDispatcher(DomainEventDispatcher):
    """Bus interno síncrono, reemplazable sin cambiar los casos de uso."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[DomainEventHandler]] = {}

    def suscribir(
        self, tipo_evento: type[DomainEvent], handler: DomainEventHandler
    ) -> None:
        self._handlers.setdefault(tipo_evento, []).append(handler)

    def despachar(self, evento: DomainEvent) -> None:
        handlers = [
            handler
            for clase in type(evento).__mro__
            for handler in self._handlers.get(clase, ())
        ]
        if not handlers:
            logger.warning("evento de dominio sin suscriptores: %s", type(evento).__name__)
            return
        for handler in handlers:
            try:
                handler.manejar(evento)
            except Exception:
                logger.exception(
                    "handler=%s falló procesando %s", type(handler).__name__, type(evento).__name__
                )
