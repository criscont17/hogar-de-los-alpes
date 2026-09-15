from dataclasses import dataclass

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class AcuerdoRenegociado(DomainEvent):
    """El acuerdo cambió. Los trabajos ya solicitados conservan las condiciones anteriores."""

    partner_id: str
