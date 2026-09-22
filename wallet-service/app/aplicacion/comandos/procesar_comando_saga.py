from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.errores import FalloSimuladoDeAcreditacionError
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.billetera import Billetera, Dinero
from app.dominio.errores import (
    BilleteraNoEncontradaError,
    MonedaInvalidaError,
    MontoInvalidoError,
)
from app.seedwork.infraestructura import PoliticaDeReintentos

logger = logging.getLogger("wallet.comandos_saga")

# Un fallo de estos no cambia por esperar: la billetera no existe, la moneda no
# corresponde o el monto es inválido. Reintentarlos solo retrasa la disputa.
ERRORES_PERMANENTES = (
    BilleteraNoEncontradaError,
    MonedaInvalidaError,
    MontoInvalidoError,
)


@dataclass(frozen=True)
class ResultadoAcreditacionSaga:
    trabajo_id: str
    proveedor_id: str
    exitoso: bool
    intentos: int
    motivo: str | None = None
    saldo_resultante: Decimal | None = None
    moneda: str | None = None


class ProcesadorComandosSagaWallet:
    """Ejecuta el paso de acreditación al proveedor dentro de la saga.

    La transacción local la delimita la unidad de trabajo, así que el saldo y su
    movimiento se confirman juntos o no se confirma ninguno. Ante un fallo que
    puede resolverse solo (billetera bloqueada que se reactiva, caída puntual de la
    base) reintenta con espera creciente; cuando los reintentos se agotan devuelve
    el fallo para que el orquestador abra la disputa, porque el trabajo físico ya
    se ejecutó y revertirlo no es una opción.
    """

    def __init__(
        self,
        fabrica_uow: Callable[[], UnidadDeTrabajo],
        dispatcher: DomainEventDispatcher,
        politica: PoliticaDeReintentos | None = None,
    ) -> None:
        self._fabrica_uow = fabrica_uow
        self._dispatcher = dispatcher
        self._politica = politica or PoliticaDeReintentos()

    @staticmethod
    def referencia(saga_id: str) -> str:
        """Identifica la acreditación de esta saga: reentregarla no la duplica."""

        return f"saga:{saga_id}:acreditacion"

    def acreditar_proveedor(
        self,
        *,
        saga_id: str,
        trabajo_id: str,
        proveedor_id: str,
        monto: Decimal,
        moneda: str,
        simular_fallo: bool = False,
    ) -> ResultadoAcreditacionSaga:
        referencia = self.referencia(saga_id)
        rechazada: Billetera | None = None
        intentos_gastados = 0

        def intento(numero: int) -> Billetera:
            nonlocal rechazada, intentos_gastados
            intentos_gastados = numero
            with self._fabrica_uow() as uow:
                billetera = uow.billeteras.obtener_por_proveedor_id(proveedor_id)
                if billetera is None:
                    raise BilleteraNoEncontradaError(
                        f"El proveedor {proveedor_id} no tiene una billetera en WalletBC"
                    )
                if billetera.tiene_movimiento_con_referencia(referencia):
                    # Comando reentregado: la acreditación de esta saga ya ocurrió.
                    return billetera

                dinero = Dinero(monto, moneda)
                if dinero.moneda != billetera.saldo.moneda:
                    raise MonedaInvalidaError(
                        f"La liquidación viene en {dinero.moneda} y la billetera opera en "
                        f"{billetera.saldo.moneda}"
                    )
                if simular_fallo:
                    raise FalloSimuladoDeAcreditacionError(
                        "Billetera bloqueada por la pasarela interna (simulación de fallo)"
                    )
                try:
                    billetera.acreditar_liquidacion(dinero, referencia)
                except Exception:
                    rechazada = billetera
                    raise
                uow.billeteras.guardar(billetera)
                uow.confirmar()
                return billetera

        try:
            billetera = self._politica.ejecutar(
                intento,
                es_recuperable=lambda exc: not isinstance(exc, ERRORES_PERMANENTES),
                al_fallar_intento=self._registrar_reintento(saga_id, trabajo_id),
            )
        except Exception as exc:
            logger.error(
                "Acreditación definitivamente fallida tras %s intento(s) para saga=%s trabajo=%s: %s",
                intentos_gastados,
                saga_id,
                trabajo_id,
                exc,
            )
            if rechazada is not None:
                # El rechazo no movió el saldo, pero el hecho sí debe observarse.
                despachar_eventos_pendientes(rechazada, self._dispatcher)
            return ResultadoAcreditacionSaga(
                trabajo_id=trabajo_id,
                proveedor_id=proveedor_id,
                exitoso=False,
                intentos=intentos_gastados,
                motivo=str(exc),
            )

        despachar_eventos_pendientes(billetera, self._dispatcher)
        return ResultadoAcreditacionSaga(
            trabajo_id=trabajo_id,
            proveedor_id=proveedor_id,
            exitoso=True,
            intentos=intentos_gastados,
            saldo_resultante=billetera.saldo.monto,
            moneda=billetera.saldo.moneda,
        )

    @staticmethod
    def _registrar_reintento(saga_id: str, trabajo_id: str):
        def registrar(intento: int, error: BaseException, espera: float) -> None:
            logger.warning(
                "Acreditación fallida (intento %s) para saga=%s trabajo=%s: %s. "
                "Reintentando en %.2fs",
                intento,
                saga_id,
                trabajo_id,
                error,
                espera,
            )

        return registrar
