from dataclasses import dataclass
from decimal import Decimal

from .evento_de_trabajo import EventoDeTrabajo, Liquidacion


@dataclass(frozen=True, kw_only=True)
class TrabajoCerrado(EventoDeTrabajo):
    """Hecho pivote: dispara la liberación del pago en PagosBC."""

    costo_total: Decimal
    moneda: str
    liquidaciones: tuple[Liquidacion, ...]
