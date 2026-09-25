from dataclasses import dataclass
from decimal import Decimal

from .evento_de_pago import EventoDePago


@dataclass(frozen=True, kw_only=True)
class PagoPendienteDeConciliacion(EventoDePago):
    """El PSP no respondió a tiempo o su circuito está abierto.

    No es un rechazo de negocio: el pago espera a que un proceso de conciliación
    diferida vuelva a intentarlo o a que un operador lo resuelva manualmente.
    """

    monto: Decimal
    moneda: str
    psp: str
    motivo: str
