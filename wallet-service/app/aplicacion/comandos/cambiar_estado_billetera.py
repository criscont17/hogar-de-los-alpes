from dataclasses import dataclass

from app.aplicacion.dtos import BilleteraDetalleDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_detalle_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import BilleteraId, EstadoBilletera
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class CambiarEstadoBilleteraCommand:
    billetera_id: str
    estado: str


class CambiarEstadoBilleteraHandler:
    """Única operación de actualización admitida sobre una billetera.

    El saldo no se edita: se mueve con `acreditar` y `debitar` para que cada peso
    quede respaldado por un movimiento. El proveedor y la moneda son parte de su
    identidad contable, así que tampoco se reasignan.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CambiarEstadoBilleteraCommand) -> BilleteraDetalleDTO:
        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_id(BilleteraId(comando.billetera_id))
            if billetera is None:
                raise BilleteraNoEncontradaError("La billetera no existe")
            if EstadoBilletera(comando.estado) is EstadoBilletera.SUSPENDIDA:
                billetera.suspender()
            else:
                billetera.reactivar()
            uow.billeteras.guardar(billetera)
            uow.confirmar()
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_detalle_dto(billetera)
