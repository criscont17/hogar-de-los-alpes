from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class AcreditacionRechazada(DomainEvent):
    """La billetera no admitió una acreditación de liquidación.

    Es el hecho que la saga necesita para decidir entre reintentar y declarar la
    disputa; el saldo y los movimientos quedan intactos.
    """

    billetera_id: str
    proveedor_id: str
    monto_solicitado: Decimal
    moneda: str
    motivo_rechazo: str
    fecha: datetime
    referencia_externa: str | None = None
