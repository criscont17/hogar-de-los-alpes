from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import Billetera, Dinero, MotivoMovimiento
from app.dominio.errores import (
    BilleteraNoEncontradaError,
    BilleteraSuspendidaError,
    FondosInsuficientesError,
)


@dataclass(frozen=True)
class RetirarSaldoProveedorCommand:
    proveedor_id: str
    monto: Decimal
    motivo: str = MotivoMovimiento.RETIRO_A_PROVEEDOR.value
    referencia_externa: str | None = None


class RetirarSaldoProveedorHandler:
    """Retiro solicitado por el proveedor, identificado por su id y no por el de la billetera.

    Es el caso de uso detrás de `POST /proveedores/{id}/wallet/retiros`: quien
    solicita el retiro conoce al proveedor, no el identificador contable de su
    billetera, que es un detalle interno de WalletBC.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: RetirarSaldoProveedorCommand) -> BilleteraDTO:
        billetera: Billetera | None = None
        try:
            with self._uow as uow:
                billetera = uow.billeteras.obtener_por_proveedor_id(comando.proveedor_id)
                if billetera is None:
                    raise BilleteraNoEncontradaError("El proveedor no tiene una billetera")
                billetera.debitar(
                    Dinero(comando.monto, billetera.saldo.moneda),
                    MotivoMovimiento(comando.motivo),
                    comando.referencia_externa,
                )
                uow.billeteras.guardar(billetera)
                uow.confirmar()
        except (FondosInsuficientesError, BilleteraSuspendidaError):
            # El retiro rechazado no mueve el saldo, pero el hecho sí se anuncia.
            despachar_eventos_pendientes(billetera, self._dispatcher)
            raise
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
