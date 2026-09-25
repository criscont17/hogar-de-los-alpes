from dataclasses import dataclass
from datetime import datetime

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class BilleteraCreada(DomainEvent):
    billetera_id: str
    proveedor_id: str
    fecha: datetime
