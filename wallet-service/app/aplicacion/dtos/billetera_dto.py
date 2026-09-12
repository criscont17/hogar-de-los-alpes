from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BilleteraDTO:
    id: str
    proveedor_id: str
    saldo: Decimal
    moneda: str
    estado: str
