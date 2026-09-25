from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class MovimientoDTO:
    id: str
    tipo: str
    motivo: str
    monto: Decimal
    saldo_resultante: Decimal
    fecha: datetime
    referencia_externa: str | None
