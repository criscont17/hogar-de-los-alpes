from dataclasses import dataclass

from app.aplicacion.dtos import MovimientoDTO
from app.aplicacion.mapeo import movimiento_a_dto
from app.dominio.billetera import BilleteraId, MovimientoId
from app.dominio.billetera.billetera_repository import BilleteraRepository
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class ObtenerMovimientoQuery:
    billetera_id: str
    movimiento_id: str


class ObtenerMovimientoHandler:
    def __init__(self, repo: BilleteraRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ObtenerMovimientoQuery) -> MovimientoDTO:
        billetera = self._repo.obtener_por_id(BilleteraId(query.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        buscado = MovimientoId(query.movimiento_id)
        for movimiento in billetera.movimientos:
            if movimiento.id == buscado:
                return movimiento_a_dto(movimiento)
        raise BilleteraNoEncontradaError("El movimiento no existe en esta billetera")
