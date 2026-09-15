from dataclasses import dataclass

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class PartnerRegistrado(DomainEvent):
    partner_id: str
    nombre: str
    pais: str
