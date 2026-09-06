from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from dominio.seedwork import DomainEvent


@dataclass(frozen=True, kw_only=True)
class SaldoAcreditado(DomainEvent):
    billetera_id: str
    monto: Decimal
    moneda: str
    saldo_resultante: Decimal
    fecha: datetime
    referencia_externa: str | None = None
