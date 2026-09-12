from dataclasses import dataclass

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.billetera import BilleteraFactory
from app.dominio.billetera.billetera_repository import BilleteraRepository
from app.dominio.errores import BilleteraDuplicadaError


@dataclass(frozen=True)
class CrearBilleteraCommand:
    proveedor_id: str
    moneda: str = "COP"


class CrearBilleteraHandler:
    def __init__(
        self,
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CrearBilleteraCommand) -> BilleteraDTO:
        if self._repo.obtener_por_proveedor_id(comando.proveedor_id) is not None:
            raise BilleteraDuplicadaError("El proveedor ya tiene una billetera")
        billetera = BilleteraFactory.crear_nueva(comando.proveedor_id, comando.moneda)
        self._repo.guardar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
