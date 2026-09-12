from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    AcreditarSaldoHandler,
    CrearBilleteraHandler,
    DebitarSaldoHandler,
    ProcesarTrabajoLiquidadoHandler,
)
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
)
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker
from app.aplicacion.queries import ListarMovimientosHandler, ObtenerSaldoHandler
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import LoggingMessageBroker
from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_billetera_repository import (
    SqlAlchemyBilleteraRepository,
)
from app.seedwork.dominio import DomainEvent


@lru_cache(maxsize=1)
def obtener_broker() -> MessageBroker:
    """Adaptador de mensajería en uso. Cambiar aquí para migrar a Rabbit o SQS."""

    return LoggingMessageBroker()


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados.

    Al estar cacheado, el registro ocurre una sola vez por proceso sin necesidad
    de banderas externas, y cada test puede pedir un bus limpio con `cache_clear()`.
    """

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    dispatcher.suscribir(
        DomainEvent, PublicarEventoDeIntegracionHandler(obtener_broker())
    )
    return dispatcher


def obtener_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyBilleteraRepository:
    return SqlAlchemyBilleteraRepository(session)


def obtener_crear_handler(
    repo=Depends(obtener_repo),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> CrearBilleteraHandler:
    return CrearBilleteraHandler(repo, dispatcher)


def obtener_acreditar_handler(
    repo=Depends(obtener_repo),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> AcreditarSaldoHandler:
    return AcreditarSaldoHandler(repo, dispatcher)


def obtener_debitar_handler(
    repo=Depends(obtener_repo),
    dispatcher: DomainEventDispatcher = Depends(obtener_dispatcher),
) -> DebitarSaldoHandler:
    return DebitarSaldoHandler(repo, dispatcher)


def obtener_saldo_handler(repo=Depends(obtener_repo)) -> ObtenerSaldoHandler:
    return ObtenerSaldoHandler(repo)


def obtener_movimientos_handler(repo=Depends(obtener_repo)) -> ListarMovimientosHandler:
    return ListarMovimientosHandler(repo)


def obtener_trabajo_liquidado_handler(
    repo=Depends(obtener_repo),
    acreditar=Depends(obtener_acreditar_handler),
) -> ProcesarTrabajoLiquidadoHandler:
    return ProcesarTrabajoLiquidadoHandler(repo, acreditar)
