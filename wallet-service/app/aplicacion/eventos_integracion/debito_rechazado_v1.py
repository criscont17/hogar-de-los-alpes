from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class DebitoRechazadoV1(IntegrationEvent):
    billetera_id: str
    monto_solicitado: str
    moneda: str
    motivo_rechazo: str
    fecha: str
    referencia_externa: str | None = None
