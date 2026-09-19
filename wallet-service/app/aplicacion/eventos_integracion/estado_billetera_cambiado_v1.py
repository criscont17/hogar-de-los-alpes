from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class EstadoBilleteraCambiadoV1(IntegrationEvent):
    billetera_id: str
    estado_anterior: str
    estado_nuevo: str
    fecha: str
