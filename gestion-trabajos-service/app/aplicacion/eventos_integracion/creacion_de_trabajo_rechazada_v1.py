from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class CreacionDeTrabajoRechazadaV1(IntegrationEvent):
    """No lleva `trabajo_id` porque el trabajo no se creó: el partner lo reconoce por su
    referencia."""

    canal: str
    partner_id: str | None = None
    referencia_externa: str | None = None
    motivo: str
