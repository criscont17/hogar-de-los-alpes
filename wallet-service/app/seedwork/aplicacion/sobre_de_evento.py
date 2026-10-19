from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class SobreDeEvento:
    """Lo que el relay del outbox entrega al transporte de mensajería.

    Desde que existe la bandeja de salida, nadie publica objetos de aplicación:
    lo que sale de la base ya es contrato serializado. El sobre añade al cuerpo
    los datos que el broker necesita para enrutar y deduplicar sin abrirlo
    —`tipo`, `event_id` y la clave de partición—, de modo que el adaptador
    concreto no tenga que interpretar el payload.
    """

    tipo: str
    event_id: UUID
    clave_particion: str | None
    payload: dict[str, Any]
