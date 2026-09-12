import logging

from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

logger = logging.getLogger("wallet.domain_events")


class AuditarEventoDeDominioHandler(DomainEventHandler[DomainEvent]):
    """Lógica interna: deja rastro de cada hecho ocurrido dentro del proceso.

    Se suscribe a `DomainEvent`, así que cubre también los eventos que se
    agreguen en el futuro sin tener que registrarlos uno por uno.
    """

    def manejar(self, evento: DomainEvent) -> None:
        logger.info(
            "domain_event=%s event_id=%s occurred_at=%s",
            type(evento).__name__,
            evento.event_id,
            evento.occurred_at.isoformat(),
        )
