from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class BilleteraDTO:
    id: str
    proveedor_id: str
    saldo: Decimal
    moneda: str
    estado: str


@dataclass(frozen=True)
class BilleteraDetalleDTO:
    """Vista administrativa: agrega los datos de gestión al saldo."""

    id: str
    proveedor_id: str
    saldo: Decimal
    moneda: str
    estado: str
    fecha_creacion: datetime
    total_movimientos: int


@dataclass(frozen=True)
class PaginaBilleterasDTO:
    items: list[BilleteraDetalleDTO]
    total: int
    limite: int
    desplazamiento: int
