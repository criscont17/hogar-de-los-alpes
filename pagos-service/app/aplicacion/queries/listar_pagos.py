from dataclasses import dataclass

from app.aplicacion.dtos import PagoDTO
from app.aplicacion.mapeo import pago_a_dto
from app.dominio.pago.pago_repository import PagoRepository

LIMITE_MAXIMO = 200


@dataclass(frozen=True)
class ListarPagosQuery:
    trabajo_id: str | None = None
    limite: int = 50


class ListarPagosHandler:
    def __init__(self, repo: PagoRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ListarPagosQuery) -> list[PagoDTO]:
        if not 1 <= query.limite <= LIMITE_MAXIMO:
            raise ValueError(f"limite debe estar entre 1 y {LIMITE_MAXIMO}")
        pagos = self._repo.listar(trabajo_id=query.trabajo_id, limite=query.limite)
        return [pago_a_dto(pago) for pago in pagos]
