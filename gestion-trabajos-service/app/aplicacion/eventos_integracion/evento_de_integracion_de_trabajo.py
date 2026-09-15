from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class EventoDeIntegracionDeTrabajo(IntegrationEvent):
    """Campos comunes a todo evento público de un trabajo.

    `partner_id` y `referencia_externa` permiten a un consumidor (o a la capa
    anti-corrupción de un partner) relacionar el hecho con su propio registro.
    """

    trabajo_id: str
    partner_id: str | None = None
    referencia_externa: str | None = None
