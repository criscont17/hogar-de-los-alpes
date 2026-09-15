from dataclasses import dataclass

from app.aplicacion.carga import cargar_partner
from app.aplicacion.dtos import PartnerDTO
from app.aplicacion.mapeo import partner_a_dto
from app.aplicacion.puertos import CatalogoDeAdaptadores
from app.dominio.partner.partner_repository import PartnerRepository


@dataclass(frozen=True)
class ObtenerPartnerQuery:
    partner_id: str


class ObtenerPartnerHandler:
    def __init__(self, repo: PartnerRepository, adaptadores: CatalogoDeAdaptadores) -> None:
        self._repo = repo
        self._adaptadores = adaptadores

    def ejecutar(self, query: ObtenerPartnerQuery) -> PartnerDTO:
        partner = cargar_partner(self._repo, query.partner_id)
        return partner_a_dto(partner, self._adaptadores.tiene(str(partner.id)))
