from dataclasses import dataclass
from decimal import Decimal

from .evento_de_pago import EventoDePago


@dataclass(frozen=True, kw_only=True)
class PagoConfirmado(EventoDePago):
    """Hecho pivote: WalletBC lo consume para acreditar saldo al proveedor."""

    monto: Decimal
    moneda: str
    psp: str
    referencia_psp: str
