from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import BilleteraId, Dinero, MotivoMovimiento
from app.dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class AcreditarSaldoCommand:
    billetera_id: str
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None


class AcreditarSaldoHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: AcreditarSaldoCommand) -> BilleteraDTO:
        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_id(BilleteraId(comando.billetera_id))
            if billetera is None:
                raise BilleteraNoEncontradaError("La billetera no existe")
            billetera.acreditar(
                Dinero(comando.monto, billetera.saldo.moneda),
                MotivoMovimiento(comando.motivo),
                comando.referencia_externa,
            )
            uow.billeteras.guardar(billetera)
            uow.confirmar()
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
