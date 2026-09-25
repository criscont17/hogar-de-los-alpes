from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.puertos import CatalogoDePSP, DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.pago import Dinero, EstadoPago, PagoFactory, TipoPago
from app.seedwork.dominio import DomainError
from app.seedwork.infraestructura import CircuitoAbiertoError


@dataclass(frozen=True)
class ResultadoComandoSagaPago:
    trabajo_id: str
    exitoso: bool
    motivo: str | None = None


class ProcesadorComandosSagaPago:
    """Ejecuta y confirma los pasos financieros de la saga en PagosBC."""

    def __init__(
        self,
        fabrica_uow: Callable[[], UnidadDeTrabajo],
        dispatcher: DomainEventDispatcher,
        adaptadores: CatalogoDePSP,
    ) -> None:
        self._fabrica_uow = fabrica_uow
        self._dispatcher = dispatcher
        self._adaptadores = adaptadores

    @staticmethod
    def _referencia(saga_id: str) -> str:
        return f"saga:{saga_id}:autorizacion"

    def autorizar(self, *, saga_id: str, trabajo_id: str, monto: Decimal, moneda: str, simular_fallo: bool) -> ResultadoComandoSagaPago:
        referencia = self._referencia(saga_id)
        pago_nuevo = None
        with self._fabrica_uow() as uow:
            pago = uow.pagos.obtener_por_referencia_externa(referencia)
            if pago is not None:
                return ResultadoComandoSagaPago(trabajo_id, pago.estado is EstadoPago.CONFIRMADO, pago.motivo)

            psp_id = self._adaptadores.psp_por_defecto(moneda)
            pago = PagoFactory.crear(
                trabajo_id=trabajo_id,
                tipo=TipoPago.COBRO_CLIENTE,
                monto=Dinero(monto, moneda),
                psp=psp_id,
                referencia_externa=referencia,
            )
            if simular_fallo:
                pago.rechazar("Fondos insuficientes (simulación de fallo)")
            else:
                try:
                    resultado = self._adaptadores.obtener(psp_id).cobrar(monto, moneda, referencia)
                    if resultado.exitoso:
                        pago.confirmar(resultado.referencia_psp or referencia)
                    else:
                        pago.rechazar(resultado.motivo or "El PSP rechazó la autorización")
                except (CircuitoAbiertoError, TimeoutError, ConnectionError, OSError, DomainError) as exc:
                    pago.rechazar(f"No fue posible autorizar el pago: {exc}")
            uow.pagos.guardar(pago)
            uow.confirmar()
            pago_nuevo = pago

        despachar_eventos_pendientes(pago_nuevo, self._dispatcher)
        return ResultadoComandoSagaPago(trabajo_id, pago_nuevo.estado is EstadoPago.CONFIRMADO, pago_nuevo.motivo)

    def revertir(self, *, saga_id: str, trabajo_id: str, motivo: str) -> ResultadoComandoSagaPago:
        referencia = self._referencia(saga_id)
        pago_revertido = None
        with self._fabrica_uow() as uow:
            pago = uow.pagos.obtener_por_referencia_externa(referencia)
            if pago is None:
                return ResultadoComandoSagaPago(trabajo_id, False, "No existe una autorización de pago para compensar")
            if pago.estado is EstadoPago.REVERSADO:
                return ResultadoComandoSagaPago(trabajo_id, True, pago.motivo)
            if pago.estado is not EstadoPago.CONFIRMADO:
                return ResultadoComandoSagaPago(trabajo_id, False, f"No se puede revertir un pago en estado {pago.estado.value}")
            pago.revertir(motivo)
            uow.pagos.guardar(pago)
            uow.confirmar()
            pago_revertido = pago

        despachar_eventos_pendientes(pago_revertido, self._dispatcher)
        return ResultadoComandoSagaPago(trabajo_id, True, motivo)
