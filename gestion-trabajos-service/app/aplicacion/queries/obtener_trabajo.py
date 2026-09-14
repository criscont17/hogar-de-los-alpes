from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.mapeo import trabajo_a_dto
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class ObtenerTrabajoQuery:
    trabajo_id: str


class ObtenerTrabajoHandler:
    def __init__(self, repo: TrabajoRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ObtenerTrabajoQuery) -> TrabajoDTO:
        return trabajo_a_dto(cargar_trabajo(self._repo, query.trabajo_id))
