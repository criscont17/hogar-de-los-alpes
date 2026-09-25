from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PagoDTO:
    id: str
    trabajo_id: str
    tipo: str
    sub_trabajo_id: str | None
    proveedor_id: str | None
    monto: Decimal
    moneda: str
    psp: str
    referencia_externa: str
    estado: str
    referencia_psp: str | None
    motivo: str | None
    fecha_creacion: datetime
