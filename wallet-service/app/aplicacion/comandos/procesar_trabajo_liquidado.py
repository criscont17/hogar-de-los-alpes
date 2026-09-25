from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import BilleteraDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import billetera_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import Dinero
from app.dominio.errores import BilleteraNoEncontradaError, MonedaInvalidaError


@dataclass(frozen=True)
class ProcesarTrabajoLiquidadoCommand:
    trabajo_id: str
    proveedor_id: str
    monto: Decimal
    moneda: str = "COP"


class ProcesarTrabajoLiquidadoHandler:
    """Acredita al proveedor la liquidación de un trabajo ya ejecutado.

    Resuelve la billetera por proveedor y acredita dentro de la misma transacción,
    para que el movimiento y el saldo nunca queden desalineados.
    """

    def __init__(self, uow: UnidadDeTrabajo, dispatcher: DomainEventDispatcher) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: ProcesarTrabajoLiquidadoCommand) -> BilleteraDTO:
        dinero = Dinero(comando.monto, comando.moneda)
        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_proveedor_id(comando.proveedor_id)
            if billetera is None:
                raise BilleteraNoEncontradaError("El proveedor no tiene una billetera")
            if dinero.moneda != billetera.saldo.moneda:
                raise MonedaInvalidaError("La moneda del evento no coincide con la billetera")
            billetera.acreditar_liquidacion(dinero, comando.trabajo_id)
            uow.billeteras.guardar(billetera)
            uow.confirmar()
        despachar_eventos_pendientes(billetera, self._dispatcher)
        return billetera_a_dto(billetera)
