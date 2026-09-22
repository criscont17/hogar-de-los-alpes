from dataclasses import dataclass

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import BilleteraFactory
from app.dominio.errores import BilleteraDuplicadaError


@dataclass(frozen=True)
class CrearBilleteraCommand:
    proveedor_id: str
    moneda: str = "COP"


class CrearBilleteraHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CrearBilleteraCommand) -> BilleteraDTO:
        with self._uow as uow:
            if uow.billeteras.obtener_por_proveedor_id(comando.proveedor_id) is not None:
                raise BilleteraDuplicadaError("El proveedor ya tiene una billetera")
            billetera = BilleteraFactory.crear_nueva(comando.proveedor_id, comando.moneda)
            uow.billeteras.guardar(billetera)
            uow.confirmar()
        # Fuera de la transacción: los eventos se anuncian cuando el hecho ya es definitivo.
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
