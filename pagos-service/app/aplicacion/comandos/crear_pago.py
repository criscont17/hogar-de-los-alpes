from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import PagoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import pago_a_dto
from app.aplicacion.puertos import CatalogoDePSP, DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.errores import PagoDuplicadoError
from app.dominio.pago import Dinero, Pago, PagoFactory, TipoPago
from app.seedwork.dominio import DomainError
from app.seedwork.infraestructura import CircuitoAbiertoError


@dataclass(frozen=True)
class CrearPagoCommand:
    trabajo_id: str
    tipo: str
    monto: Decimal
    moneda: str
    referencia_externa: str
    sub_trabajo_id: str | None = None
    proveedor_id: str | None = None
    psp: str | None = None


class CrearPagoHandler:
    """Crea un pago y lo intenta de inmediato contra el PSP correspondiente.

    - Es idempotente por `referencia_externa`: reintentar el mismo checkout, o
      que Pulsar reentregue `TrabajoCerradoV1`, nunca duplica el cobro/pago.
    - El PSP se resuelve por moneda salvo que el llamador fuerce uno (`psp`).
    - Éxito → `Pago.confirmar`. Rechazo de negocio del PSP → `Pago.rechazar`.
      Circuito abierto o timeout → `Pago.marcar_pendiente_de_conciliacion`: no
      es un fallo del pago, es un PSP que no respondió a tiempo.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
        adaptadores: CatalogoDePSP,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher
        self._adaptadores = adaptadores

    def ejecutar(self, comando: CrearPagoCommand) -> PagoDTO:
        with self._uow as uow:
            existente = uow.pagos.obtener_por_referencia_externa(comando.referencia_externa)
            if existente is not None:
                return pago_a_dto(existente)

            psp_id = comando.psp or self._adaptadores.psp_por_defecto(comando.moneda)
            pago = PagoFactory.crear(
                trabajo_id=comando.trabajo_id,
                tipo=TipoPago(comando.tipo),
                monto=Dinero(comando.monto, comando.moneda),
                psp=psp_id,
                referencia_externa=comando.referencia_externa,
                sub_trabajo_id=comando.sub_trabajo_id,
                proveedor_id=comando.proveedor_id,
            )
            self._intentar_cobro(pago)

            try:
                uow.pagos.guardar(pago)
                uow.confirmar()
            except PagoDuplicadoError:
                # Dos entregas simultáneas de la misma referencia: otra ganó la carrera.
                # `flush()` pudo haber fallado antes de llegar a `confirmar()`, por
                # lo que la sesión debe volver a un estado consultable antes de leer
                # el pago que confirmó la otra entrega.
                uow.revertir()
                existente = uow.pagos.obtener_por_referencia_externa(comando.referencia_externa)
                if existente is None:
                    raise
                return pago_a_dto(existente)

        despachar_eventos_pendientes(pago, self._dispatcher)
        return pago_a_dto(pago)


    def _intentar_cobro(self, pago: Pago) -> None:
        adaptador = self._adaptadores.obtener(pago.psp)
        try:
            resultado = adaptador.cobrar(pago.monto.monto, pago.monto.moneda, pago.referencia_externa)
        except DomainError:
            raise
        except (CircuitoAbiertoError, TimeoutError, ConnectionError, OSError) as exc:
            # Circuito abierto, timeout o una caída puntual del PSP (antes de que
            # el circuito alcance su umbral de fallos): en los tres casos el PSP
            # no confirmó la operación, así que el pago espera conciliación
            # diferida en vez de quedar en un estado indefinido.
            pago.marcar_pendiente_de_conciliacion(str(exc))
            return
        if resultado.exitoso:
            pago.confirmar(resultado.referencia_psp or pago.referencia_externa)
        else:
            pago.rechazar(resultado.motivo or "El PSP rechazó la operación")
