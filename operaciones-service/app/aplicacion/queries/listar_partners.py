from dataclasses import dataclass

from app.aplicacion.dtos import PartnerDTO
from app.aplicacion.mapeo import partner_a_dto
from app.aplicacion.puertos import CatalogoDeAdaptadores
from app.dominio.partner.partner_repository import PartnerRepository


@dataclass(frozen=True)
class ListarPartnersQuery:
    pass


class ListarPartnersHandler:
    def __init__(self, repo: PartnerRepository, adaptadores: CatalogoDeAdaptadores) -> None:
        self._repo = repo
        self._adaptadores = adaptadores

    def ejecutar(self, query: ListarPartnersQuery) -> list[PartnerDTO]:
        return [
            partner_a_dto(partner, self._adaptadores.tiene(str(partner.id)))
            for partner in self._repo.listar()
        ]
