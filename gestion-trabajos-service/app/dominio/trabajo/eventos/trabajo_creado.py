from dataclasses import dataclass
from decimal import Decimal

from .evento_de_trabajo import DetalleSubTrabajo, EventoDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoCreado(EventoDeTrabajo):
    canal: str
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    moneda: str
    monto_maximo: Decimal | None
    sla_horas: int | None
    sub_trabajos: tuple[DetalleSubTrabajo, ...]
