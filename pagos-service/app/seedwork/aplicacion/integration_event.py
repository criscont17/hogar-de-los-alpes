import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from app.seedwork.dominio.domain_event import utc_now

_NOMBRE_VERSIONADO = re.compile(r"^(?P<tipo>.+)V(?P<version>\d+)$")


@dataclass(frozen=True, kw_only=True)
class IntegrationEvent:
    """Hecho publicado hacia otros bounded contexts.

    A diferencia de un `DomainEvent`, su esquema es contrato público: se versiona
    en el nombre de la clase (`PagoConfirmadoV1`) y solo evoluciona de forma
    retrocompatible. Por eso sus campos usan tipos primitivos serializables.

    `deprecado` marca una versión que sigue publicándose mientras sus
    consumidores migran a la siguiente; viaja como metadato del mensaje.
    """

    deprecado: ClassVar[bool] = False

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=utc_now)

    @property
    def nombre(self) -> str:
        """Nombre con el que viaja el evento por la plataforma de mensajería."""
        return type(self).__name__

    @property
    def tipo(self) -> str:
        """Nombre del hecho sin versión: `PagoConfirmadoV1` → `PagoConfirmado`."""
        coincidencia = _NOMBRE_VERSIONADO.match(self.nombre)
        return coincidencia.group("tipo") if coincidencia else self.nombre

    @property
    def version(self) -> int:
        coincidencia = _NOMBRE_VERSIONADO.match(self.nombre)
        return int(coincidencia.group("version")) if coincidencia else 1

    def como_diccionario(self) -> dict[str, Any]:
        datos = asdict(self)
        datos["event_id"] = str(self.event_id)
        datos["occurred_at"] = self.occurred_at.isoformat()
        return datos
