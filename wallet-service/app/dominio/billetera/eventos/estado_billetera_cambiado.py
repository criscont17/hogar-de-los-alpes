from dataclasses import dataclass
from datetime import datetime

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EstadoBilleteraCambiado(DomainEvent):
    billetera_id: str
    estado_anterior: str
    estado_nuevo: str
    fecha: datetime
