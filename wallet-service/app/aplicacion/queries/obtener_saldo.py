from dataclasses import dataclass

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.mapeo import billetera_a_dto
from app.dominio.billetera import BilleteraId
from app.dominio.billetera.billetera_repository import BilleteraRepository
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class ObtenerSaldoQuery:
    billetera_id: str


class ObtenerSaldoHandler:
    def __init__(self, repo: BilleteraRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ObtenerSaldoQuery) -> BilleteraDTO:
        billetera = self._repo.obtener_por_id(BilleteraId(query.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        return billetera_a_dto(billetera)
