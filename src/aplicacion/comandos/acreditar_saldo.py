from dataclasses import dataclass
from decimal import Decimal

from aplicacion.dtos import BilleteraDTO
from aplicacion.eventos import despachar_eventos_pendientes
from aplicacion.mapeo import billetera_a_dto
from aplicacion.puertos import DomainEventDispatcher, EventPublisher
from dominio.billetera import BilleteraId, Dinero, MotivoMovimiento
from dominio.billetera.billetera_repository import BilleteraRepository
from dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class AcreditarSaldoCommand:
    billetera_id: str
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None


class AcreditarSaldoHandler:
    def __init__(
        self,
        repo: BilleteraRepository,
        dispatcher: DomainEventDispatcher,
        publisher: EventPublisher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher
        self._publisher = publisher

    def ejecutar(self, comando: AcreditarSaldoCommand) -> BilleteraDTO:
        billetera = self._repo.obtener_por_id(BilleteraId(comando.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        billetera.acreditar(
            Dinero(comando.monto, billetera.saldo.moneda),
            MotivoMovimiento(comando.motivo),
            comando.referencia_externa,
        )
        self._repo.guardar(billetera)
        despachar_eventos_pendientes(billetera, self._dispatcher, self._publisher)
        return billetera_a_dto(billetera)
