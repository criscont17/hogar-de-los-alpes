from dataclasses import dataclass
from decimal import Decimal

from .evento_de_trabajo import EventoDeTrabajo


@dataclass(frozen=True, kw_only=True)
class AsignacionRechazada(EventoDeTrabajo):
    """El acuerdo impidió asignar: proveedor fuera de la red o sobrecosto."""

    sub_trabajo_id: str
    proveedor_id: str
    monto_cotizado: Decimal
    moneda: str
    motivo_rechazo: str
