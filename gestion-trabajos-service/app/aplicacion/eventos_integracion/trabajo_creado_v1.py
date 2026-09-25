from dataclasses import dataclass
from typing import Any, ClassVar

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoCreadoV1(EventoDeIntegracionDeTrabajo):
    """Primera versión del contrato. Deprecada: se sigue publicando mientras sus
    consumidores migran a `TrabajoCreadoV2`."""

    deprecado: ClassVar[bool] = True

    canal: str
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    moneda: str
    sub_trabajos: tuple[dict[str, Any], ...]
