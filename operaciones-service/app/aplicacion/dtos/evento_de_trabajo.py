from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventoDeTrabajoRecibido:
    """Hecho publicado por GestionDeTrabajosBC, tal como llega por la plataforma de mensajería.

    OperacionesBC no importa clases de otro bounded context: trabaja sobre su contrato
    público, un nombre versionado (`TrabajoCerradoV1`) y campos primitivos.
    """

    nombre: str
    datos: Mapping[str, Any]

    @property
    def partner_id(self) -> str | None:
        return self.datos.get("partner_id")

    @property
    def referencia_externa(self) -> str | None:
        return self.datos.get("referencia_externa")

    @property
    def trabajo_id(self) -> str | None:
        return self.datos.get("trabajo_id")

    @property
    def event_id(self) -> str:
        return str(self.datos.get("event_id", ""))

    @property
    def occurred_at(self) -> str:
        return str(self.datos.get("occurred_at", ""))
