import json
import logging
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from dominio.seedwork import DomainEvent

logger = logging.getLogger("wallet.integration_events")


def _serializar(valor: object) -> str:
    if isinstance(valor, (date, datetime, Decimal, UUID, Enum)):
        return str(valor.value if isinstance(valor, Enum) else valor)
    raise TypeError(f"No se puede serializar {type(valor).__name__}")


class LoggingEventPublisher:
    """Adaptador simulado del puerto de integración; Kafka puede sustituirlo."""

    def publicar(self, evento: DomainEvent) -> None:
        envelope = {
            "event_type": type(evento).__name__,
            "payload": asdict(evento),
        }
        logger.info("integration_event=%s", json.dumps(envelope, default=_serializar))
