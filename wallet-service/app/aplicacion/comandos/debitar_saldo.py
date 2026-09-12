from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.billetera import BilleteraId, Dinero, MotivoMovimiento
from app.dominio.billetera.billetera_repository import BilleteraRepository
from app.dominio.errores import (
    BilleteraNoEncontradaError,
    BilleteraSuspendidaError,
    FondosInsuficientesError,
)


@dataclass(frozen=True)
class DebitarSaldoCommand:
    billetera_id: str
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None


class DebitarSaldoHandler:
    def __init__(
        self,
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: DebitarSaldoCommand) -> BilleteraDTO:
        billetera = self._repo.obtener_por_id(BilleteraId(comando.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        try:
            billetera.debitar(
                Dinero(comando.monto, billetera.saldo.moneda),
                MotivoMovimiento(comando.motivo),
                comando.referencia_externa,
            )
        except (FondosInsuficientesError, BilleteraSuspendidaError):
            # El rechazo no cambia el agregado, pero su evento sí debe observarse.
            despachar_eventos_pendientes(billetera, self._dispatcher)
            raise
        self._repo.guardar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
