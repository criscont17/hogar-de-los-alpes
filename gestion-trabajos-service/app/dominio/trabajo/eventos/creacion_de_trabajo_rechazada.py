from dataclasses import dataclass

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class CreacionDeTrabajoRechazada(DomainEvent):
    """La solicitud no formó un trabajo válido y no se creó nada.

    No sale de un agregado porque el agregado no llegó a existir: lo registra el caso de uso
    de creación para que el canal que lo pidió (Marketplace u OperacionesBC) se entere
    aunque haya enviado la solicitud por mensajería.
    """

    canal: str
    partner_id: str | None = None
    referencia_externa: str | None = None
    motivo: str
