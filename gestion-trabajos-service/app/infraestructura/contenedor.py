"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de comandos de
Pulsar), por eso vive fuera de `entrada/api`. Las instancias se cachean: el bus y el
broker existen una sola vez por proceso, y `reiniciar()` los libera al apagar.
"""

from functools import lru_cache
from typing import Any

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
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker, UnidadDeTrabajo
from app.aplicacion.sagas.orquestador_saga_trabajo import OrquestadorSagaTrabajo
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    LoggingMessageBroker,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.mensajeria.pulsar_saga_command_publisher import (
    PulsarSagaCommandPublisher,
)
from app.infraestructura.adaptadores.salida.persistencia.db import SessionLocal
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_saga_log_repository import (
    SqlAlchemySagaLogRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
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


def unidad_de_trabajo() -> UnidadDeTrabajo:
    """Nueva unidad de trabajo: aquí se decide la tecnología de la transacción.

    Se crea una por petición HTTP o por mensaje de Pulsar, porque cada una abre y cierra
    su propia sesión de base de datos.
    """
    return SqlAlchemyUnidadDeTrabajo()


@lru_cache(maxsize=1)
def obtener_saga_log_repo() -> SqlAlchemySagaLogRepository:
    return SqlAlchemySagaLogRepository(SessionLocal)


@lru_cache(maxsize=1)
def obtener_saga_command_publisher() -> PulsarSagaCommandPublisher:
    return PulsarSagaCommandPublisher(PULSAR_URL)


@lru_cache(maxsize=1)
def obtener_orquestador_saga() -> OrquestadorSagaTrabajo:
    saga_log_repo = obtener_saga_log_repo()
    publisher = obtener_saga_command_publisher()
    return OrquestadorSagaTrabajo(
        saga_log_repo=saga_log_repo,
        fabrica_uow=unidad_de_trabajo,
        command_publisher=publisher,
        topico_comandos_pago=PULSAR_TOPICO_COMANDOS_PAGO,
        topico_comandos_operaciones=PULSAR_TOPICO_COMANDOS_OPERACIONES,
    )


def handlers_de_comandos(uow: UnidadDeTrabajo) -> dict[type, Any]:
    """Casos de uso de escritura; `uow` delimita la transacción de cada uno."""

    dispatcher = obtener_dispatcher()
    return {
        CrearTrabajoCommand: CrearTrabajoHandler(uow, dispatcher),
        AsignarProveedorCommand: AsignarProveedorHandler(uow, dispatcher),
        IniciarSubTrabajoCommand: IniciarSubTrabajoHandler(uow, dispatcher),
        CompletarSubTrabajoCommand: CompletarSubTrabajoHandler(uow, dispatcher),
        RegistrarRediagnosticoCommand: RegistrarRediagnosticoHandler(uow, dispatcher),
        CancelarTrabajoCommand: CancelarTrabajoHandler(uow, dispatcher),
        CerrarTrabajoCommand: CerrarTrabajoHandler(uow, dispatcher),
    }


def reiniciar() -> None:
    """Cierra el broker y limpia las cachés."""

    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    obtener_saga_log_repo.cache_clear()
    obtener_saga_command_publisher.cache_clear()
    obtener_orquestador_saga.cache_clear()
