"""Cableado de la API REST sobre la raíz de composición del servicio.

Los adaptadores compartidos (bus de eventos y broker) se piden al contenedor, que
es el mismo que usa el consumidor de comandos de saga: así un comando produce los
mismos efectos llegue por HTTP o por Pulsar. Lo que sí es propio de cada petición
es la transacción, por eso `obtener_uow` crea una unidad de trabajo nueva cada vez.
"""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    AcreditarSaldoHandler,
    CambiarEstadoBilleteraHandler,
    CrearBilleteraHandler,
    DebitarSaldoHandler,
    EliminarBilleteraHandler,
    ProcesarTrabajoLiquidadoHandler,
    RetirarSaldoProveedorHandler,
)
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker, UnidadDeTrabajo
from app.aplicacion.queries import (
    ListarBilleterasHandler,
    ListarMovimientosHandler,
    ObtenerBilleteraHandler,
    ObtenerMovimientoHandler,
    ObtenerSaldoHandler,
)
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_billetera_repository import (
    SqlAlchemyBilleteraRepository,
)


def obtener_broker() -> MessageBroker:
    return contenedor.obtener_broker()


def obtener_dispatcher() -> DomainEventDispatcher:
    return contenedor.obtener_dispatcher()


def obtener_uow() -> UnidadDeTrabajo:
    """Una unidad de trabajo por petición: abre y cierra su propia sesión."""

    return contenedor.unidad_de_trabajo()


def obtener_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyBilleteraRepository:
    """Repositorio de solo lectura para las queries, fuera de toda transacción de escritura."""

    return SqlAlchemyBilleteraRepository(session)


def obtener_crear_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> CrearBilleteraHandler:
    return CrearBilleteraHandler(uow, dispatcher)


def obtener_acreditar_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> AcreditarSaldoHandler:
    return AcreditarSaldoHandler(uow, dispatcher)


def obtener_debitar_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> DebitarSaldoHandler:
    return DebitarSaldoHandler(uow, dispatcher)


def obtener_retiro_proveedor_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> RetirarSaldoProveedorHandler:
    return RetirarSaldoProveedorHandler(uow, dispatcher)


def obtener_cambiar_estado_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> CambiarEstadoBilleteraHandler:
    return CambiarEstadoBilleteraHandler(uow, dispatcher)


def obtener_eliminar_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> EliminarBilleteraHandler:
    return EliminarBilleteraHandler(uow, dispatcher)


def obtener_trabajo_liquidado_handler(
    uow: UnidadDeTrabajo = Depends(obtener_uow),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> ProcesarTrabajoLiquidadoHandler:
    return ProcesarTrabajoLiquidadoHandler(uow, dispatcher)


def obtener_saldo_handler(repo=Depends(obtener_repo)) -> ObtenerSaldoHandler:
    return ObtenerSaldoHandler(repo)


def obtener_billetera_handler(repo=Depends(obtener_repo)) -> ObtenerBilleteraHandler:
    return ObtenerBilleteraHandler(repo)


def obtener_listar_billeteras_handler(
    repo=Depends(obtener_repo),
) -> ListarBilleterasHandler:
    return ListarBilleterasHandler(repo)


def obtener_movimientos_handler(repo=Depends(obtener_repo)) -> ListarMovimientosHandler:
    return ListarMovimientosHandler(repo)


def obtener_movimiento_handler(repo=Depends(obtener_repo)) -> ObtenerMovimientoHandler:
    return ObtenerMovimientoHandler(repo)
