import logging

from app.seedwork.aplicacion import DomainEventHandler
from app.seedwork.dominio import DomainEvent

logger = logging.getLogger("operaciones.domain_events")


class AuditarEventoDeDominioHandler(DomainEventHandler[DomainEvent]):
    """Deja rastro de cada hecho del dominio: registros de partners y renegociaciones."""

    def manejar(self, evento: DomainEvent) -> None:
        logger.info(
            "domain_event=%s event_id=%s occurred_at=%s",
            type(evento).__name__,
            evento.event_id,
            evento.occurred_at.isoformat(),
        )
