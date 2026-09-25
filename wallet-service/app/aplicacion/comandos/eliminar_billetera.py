from dataclasses import dataclass

from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import BilleteraId
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class EliminarBilleteraCommand:
    billetera_id: str


class EliminarBilleteraHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: EliminarBilleteraCommand) -> None:
        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_id(BilleteraId(comando.billetera_id))
            if billetera is None:
                raise BilleteraNoEncontradaError("La billetera no existe")
            # El agregado valida primero: si la regla falla no se toca la base.
            billetera.confirmar_eliminacion()
            uow.billeteras.eliminar(billetera)
            uow.confirmar()
        despachar_eventos_pendientes(billetera, self._dispatcher)
