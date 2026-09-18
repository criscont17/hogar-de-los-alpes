"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de comandos de
Pulsar), por eso vive fuera de `entrada/api`. Las instancias se cachean: el bus y el
broker existen una sola vez por proceso, y `reiniciar()` los libera al apagar.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    AsignarProveedorCommand,
    AsignarProveedorHandler,
    CancelarTrabajoCommand,
    CancelarTrabajoHandler,
    CerrarTrabajoCommand,
    CerrarTrabajoHandler,
    CompletarSubTrabajoCommand,
    CompletarSubTrabajoHandler,
    CrearTrabajoCommand,
    CrearTrabajoHandler,
    IniciarSubTrabajoCommand,
    IniciarSubTrabajoHandler,
    RegistrarRediagnosticoCommand,
    RegistrarRediagnosticoHandler,
)
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
)
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    LoggingMessageBroker,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.persistencia.db import session_factory
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_saga_log_repository import (
    SqlAlchemySagaLogRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajo_repository import (
    SqlAlchemyTrabajoRepository,
)
from app.infraestructura.adaptadores.salida.mensajeria.pulsar_saga_command_publisher import (
    PulsarSagaCommandPublisher,
)
from app.aplicacion.sagas.orquestador_saga_trabajo import OrquestadorSagaTrabajo
from app.infraestructura.configuracion import (
    MESSAGE_BROKER,
    PULSAR_TOPICO_COMANDOS_OPERACIONES,
    PULSAR_TOPICO_COMANDOS_PAGO,
    PULSAR_TOPICO_EVENTOS,
    PULSAR_URL,
)
from app.seedwork.dominio import DomainEvent


@lru_cache(maxsize=1)
def obtener_broker() -> MessageBroker:
    """Adaptador de mensajería en uso según `MESSAGE_BROKER`."""

    if MESSAGE_BROKER == "pulsar":
        return PulsarMessageBroker(PULSAR_URL, PULSAR_TOPICO_EVENTOS)
    if MESSAGE_BROKER == "memoria":
        return InMemoryMessageBroker()
    return LoggingMessageBroker()


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados, una vez por proceso."""

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    dispatcher.suscribir(DomainEvent, PublicarEventoDeIntegracionHandler(obtener_broker()))
    return dispatcher


@lru_cache(maxsize=1)
def obtener_saga_log_repo() -> SqlAlchemySagaLogRepository:
    return SqlAlchemySagaLogRepository(session_factory)


@lru_cache(maxsize=1)
def obtener_saga_command_publisher() -> PulsarSagaCommandPublisher:
    return PulsarSagaCommandPublisher(PULSAR_URL)


@lru_cache(maxsize=1)
def obtener_orquestador_saga() -> OrquestadorSagaTrabajo:
    session = session_factory()
    trabajo_repo = SqlAlchemyTrabajoRepository(session)
    saga_log_repo = obtener_saga_log_repo()
    publisher = obtener_saga_command_publisher()
    return OrquestadorSagaTrabajo(
        saga_log_repo=saga_log_repo,
        trabajo_repo=trabajo_repo,
        command_publisher=publisher,
        topico_comandos_pago=PULSAR_TOPICO_COMANDOS_PAGO,
        topico_comandos_operaciones=PULSAR_TOPICO_COMANDOS_OPERACIONES,
    )


def handlers_de_comandos(session: Session) -> dict[type, Any]:
    """Casos de uso de escritura, con un repositorio atado a `session`."""

    repo = SqlAlchemyTrabajoRepository(session)
    dispatcher = obtener_dispatcher()
    return {
        CrearTrabajoCommand: CrearTrabajoHandler(repo, dispatcher),
        AsignarProveedorCommand: AsignarProveedorHandler(repo, dispatcher),
        IniciarSubTrabajoCommand: IniciarSubTrabajoHandler(repo, dispatcher),
        CompletarSubTrabajoCommand: CompletarSubTrabajoHandler(repo, dispatcher),
        RegistrarRediagnosticoCommand: RegistrarRediagnosticoHandler(repo, dispatcher),
        CancelarTrabajoCommand: CancelarTrabajoHandler(repo, dispatcher),
        CerrarTrabajoCommand: CerrarTrabajoHandler(repo, dispatcher),
    }


def reiniciar() -> None:
    """Cierra el broker y limpia las cachés."""

    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    if obtener_saga_command_publisher.cache_info().currsize:
        obtener_saga_command_publisher().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    obtener_saga_log_repo.cache_clear()
    obtener_saga_command_publisher.cache_clear()
    obtener_orquestador_saga.cache_clear()

