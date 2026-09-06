from dataclasses import dataclass

from aplicacion.dtos import BilleteraDTO
from aplicacion.eventos import despachar_eventos_pendientes
from aplicacion.mapeo import billetera_a_dto
from aplicacion.puertos import DomainEventDispatcher, EventPublisher
from dominio.billetera import BilleteraFactory
from dominio.billetera.billetera_repository import BilleteraRepository
from dominio.errores import BilleteraDuplicadaError


@dataclass(frozen=True)
class CrearBilleteraCommand:
    proveedor_id: str
    moneda: str = "COP"


class CrearBilleteraHandler:
    def __init__(
        self,
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
        publisher: EventPublisher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher
        self._publisher = publisher

    def ejecutar(self, comando: CrearBilleteraCommand) -> BilleteraDTO:
        if self._repo.obtener_por_proveedor_id(comando.proveedor_id) is not None:
            raise BilleteraDuplicadaError("El proveedor ya tiene una billetera")
        billetera = BilleteraFactory.crear_nueva(comando.proveedor_id, comando.moneda)
        self._repo.guardar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher, self._publisher)
        return billetera_a_dto(billetera)
