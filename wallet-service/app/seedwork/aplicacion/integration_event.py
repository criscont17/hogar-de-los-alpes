from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.seedwork.dominio.domain_event import utc_now


@dataclass(frozen=True, kw_only=True)
class IntegrationEvent:
    """Hecho publicado hacia otros bounded contexts.

    A diferencia de un `DomainEvent`, su esquema es contrato público: se versiona
    en el nombre de la clase y solo debe evolucionar de forma retrocompatible.
    Por eso sus campos usan tipos primitivos serializables y no objetos del dominio.
    """

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=utc_now)

    @property
    def nombre(self) -> str:
        """Nombre con el que viaja el evento por la plataforma de mensajería."""
        return type(self).__name__

    def como_diccionario(self) -> dict[str, Any]:
        datos = asdict(self)
        datos["event_id"] = str(self.event_id)
        datos["occurred_at"] = self.occurred_at.isoformat()
        return datos
