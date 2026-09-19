from dataclasses import dataclass

from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.billetera import BilleteraId
from app.dominio.billetera.billetera_repository import BilleteraRepository
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class EliminarBilleteraCommand:
    billetera_id: str


class EliminarBilleteraHandler:
    def __init__(
        self,
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: EliminarBilleteraCommand) -> None:
        billetera = self._repo.obtener_por_id(BilleteraId(comando.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        # El agregado valida primero: si la regla falla no se toca la base.
        billetera.confirmar_eliminacion()
        self._repo.eliminar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher)
