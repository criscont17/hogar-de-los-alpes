import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from aplicacion.comandos import (
    AcreditarSaldoHandler,
    CrearBilleteraHandler,
    DebitarSaldoHandler,
    ProcesarTrabajoLiquidadoHandler,
)
from aplicacion.queries import ListarMovimientosHandler, ObtenerSaldoHandler
from dominio.seedwork import DomainEvent
from infraestructura.adaptadores.salida.eventos import (
    InMemoryDomainEventDispatcher,
    LoggingEventPublisher,
)
from infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from infraestructura.adaptadores.salida.persistencia.sqlalchemy_billetera_repository import (
    SqlAlchemyBilleteraRepository,
)

logger = logging.getLogger("wallet.domain_events")
dispatcher = InMemoryDomainEventDispatcher()
publisher = LoggingEventPublisher()


def _auditar_evento(evento: DomainEvent) -> None:
    logger.info("domain_event=%s event_id=%s", type(evento).__name__, evento.event_id)


def obtener_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyBilleteraRepository:
    return SqlAlchemyBilleteraRepository(session)


def obtener_crear_handler(repo=Depends(obtener_repo)) -> CrearBilleteraHandler:
    return CrearBilleteraHandler(repo, dispatcher, publisher)


def obtener_acreditar_handler(repo=Depends(obtener_repo)) -> AcreditarSaldoHandler:
    return AcreditarSaldoHandler(repo, dispatcher, publisher)


def obtener_debitar_handler(repo=Depends(obtener_repo)) -> DebitarSaldoHandler:
    return DebitarSaldoHandler(repo, dispatcher, publisher)


def obtener_saldo_handler(repo=Depends(obtener_repo)) -> ObtenerSaldoHandler:
    return ObtenerSaldoHandler(repo)


def obtener_movimientos_handler(repo=Depends(obtener_repo)) -> ListarMovimientosHandler:
    return ListarMovimientosHandler(repo)


def obtener_trabajo_liquidado_handler(
    repo=Depends(obtener_repo),
    acreditar=Depends(obtener_acreditar_handler),
) -> ProcesarTrabajoLiquidadoHandler:
    return ProcesarTrabajoLiquidadoHandler(repo, acreditar)


def registrar_manejadores_internos() -> None:
    if getattr(dispatcher, "_wallet_handlers_registered", False):
        return
    from dominio.billetera.eventos import (
        BilleteraCreada,
        DebitoRechazado,
        SaldoAcreditado,
        SaldoDebitado,
    )

    for event_type in (BilleteraCreada, SaldoAcreditado, SaldoDebitado, DebitoRechazado):
        dispatcher.registrar(event_type, _auditar_evento)
    dispatcher._wallet_handlers_registered = True
