from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import (
    anunciar_hechos,
    encolar_eventos_pendientes,
    registrar_hechos,
)
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import Billetera, BilleteraId, Dinero, MotivoMovimiento
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
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: DebitarSaldoCommand) -> BilleteraDTO:
        billetera: Billetera | None = None
        try:
            with self._uow as uow:
                billetera = uow.billeteras.obtener_por_id(BilleteraId(comando.billetera_id))
                if billetera is None:
                    raise BilleteraNoEncontradaError("La billetera no existe")
                billetera.debitar(
                    Dinero(comando.monto, billetera.saldo.moneda),
                    MotivoMovimiento(comando.motivo),
                    comando.referencia_externa,
                )
                uow.billeteras.guardar(billetera)
                hechos = encolar_eventos_pendientes(billetera, uow)
                uow.confirmar()
        except (FondosInsuficientesError, BilleteraSuspendidaError):
            # El rechazo no cambia el agregado, pero su evento sí debe observarse.
            # La transacción anterior ya se revirtió: el aviso abre la suya.
            registrar_hechos(billetera, self._uow, self._dispatcher)
            raise
        anunciar_hechos(hechos, self._dispatcher)
        return billetera_a_dto(billetera)
