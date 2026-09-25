from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class SaldoDebitado(DomainEvent):
    billetera_id: str
    monto: Decimal
    moneda: str
    motivo: str
    saldo_resultante: Decimal
    fecha: datetime
    referencia_externa: str | None = None
