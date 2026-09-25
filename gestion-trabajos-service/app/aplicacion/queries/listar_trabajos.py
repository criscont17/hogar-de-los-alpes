from dataclasses import dataclass

from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.mapeo import trabajo_a_dto
from app.dominio.trabajo import EstadoTrabajo
from app.dominio.trabajo.trabajo_repository import TrabajoRepository

LIMITE_MAXIMO = 200


@dataclass(frozen=True)
class ListarTrabajosQuery:
    estado: str | None = None
    partner_id: str | None = None
    limite: int = 50


class ListarTrabajosHandler:
    def __init__(self, repo: TrabajoRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ListarTrabajosQuery) -> list[TrabajoDTO]:
        if not 1 <= query.limite <= LIMITE_MAXIMO:
            raise ValueError(f"limite debe estar entre 1 y {LIMITE_MAXIMO}")
        estado = EstadoTrabajo(query.estado) if query.estado else None
        trabajos = self._repo.listar(estado=estado, partner_id=query.partner_id, limite=query.limite)
        return [trabajo_a_dto(trabajo) for trabajo in trabajos]
