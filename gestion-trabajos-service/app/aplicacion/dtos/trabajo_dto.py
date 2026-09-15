from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class SubTrabajoDTO:
    id: str
    categoria: str
    descripcion: str
    estado: str
    depende_de: tuple[str, ...]
    proveedor_id: str | None
    monto_cotizado: Decimal | None
    evidencias: tuple[str, ...]


@dataclass(frozen=True)
class TrabajoDTO:
    id: str
    canal: str
    partner_id: str | None
    referencia_externa: str | None
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    estado: str
    costo_total: Decimal
    monto_maximo: Decimal | None
    sla_horas: int | None
    fecha_creacion: datetime
    sub_trabajos: tuple[SubTrabajoDTO, ...]
