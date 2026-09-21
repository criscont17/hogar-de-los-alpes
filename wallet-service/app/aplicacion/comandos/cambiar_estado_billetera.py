from dataclasses import dataclass

from app.aplicacion.dtos import BilleteraDetalleDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_detalle_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.billetera import BilleteraId, EstadoBilletera
from app.dominio.billetera.billetera_repository import BilleteraRepository
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
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CambiarEstadoBilleteraCommand) -> BilleteraDetalleDTO:
        billetera = self._repo.obtener_por_id(BilleteraId(comando.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        if EstadoBilletera(comando.estado) is EstadoBilletera.SUSPENDIDA:
            billetera.suspender()
        else:
            billetera.reactivar()
        self._repo.guardar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_detalle_dto(billetera)
