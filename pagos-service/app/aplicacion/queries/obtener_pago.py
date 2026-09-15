from dataclasses import dataclass

from app.aplicacion.carga import cargar_pago
from app.aplicacion.dtos import PagoDTO
from app.aplicacion.mapeo import pago_a_dto
from app.dominio.pago.pago_repository import PagoRepository


@dataclass(frozen=True)
class ObtenerPagoQuery:
    pago_id: str


class ObtenerPagoHandler:
    def __init__(self, repo: PagoRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ObtenerPagoQuery) -> PagoDTO:
        return pago_a_dto(cargar_pago(self._repo, query.pago_id))
