from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class BilleteraCreadaV1(IntegrationEvent):
    billetera_id: str
    proveedor_id: str
    fecha: str
