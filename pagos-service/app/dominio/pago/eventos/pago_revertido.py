from dataclasses import dataclass
from decimal import Decimal

from .evento_de_pago import EventoDePago


@dataclass(frozen=True, kw_only=True)
class PagoRevertido(EventoDePago):
    monto: Decimal
    moneda: str
    psp: str
    motivo: str
