from dataclasses import dataclass
from decimal import Decimal

from .solicitud_de_partner import SubTrabajoSolicitado


@dataclass(frozen=True)
class SolicitudDeCreacionDeTrabajo:
    """Lo que OperacionesBC le pide a GestionDeTrabajosBC: el trabajo en términos canónicos
    más las condiciones del acuerdo ya resueltas."""

    partner_id: str
    referencia_externa: str
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    sub_trabajos: tuple[SubTrabajoSolicitado, ...]
    sla_horas: int
    monto_maximo: Decimal | None
    proveedores_permitidos: frozenset[str] | None
