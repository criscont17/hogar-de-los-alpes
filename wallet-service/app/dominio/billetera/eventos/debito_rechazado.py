from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class DebitoRechazado(DomainEvent):
    billetera_id: str
    monto_solicitado: Decimal
    moneda: str
    motivo_rechazo: str
    fecha: datetime
    referencia_externa: str | None = None
