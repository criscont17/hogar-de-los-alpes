"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de comandos de
Pulsar), por eso vive fuera de `entrada/api`. Las instancias se cachean: bus,
broker y catálogo de partners existen una sola vez por proceso, y `reiniciar()`
los libera al apagar el servicio o entre pruebas.
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
    CrearTrabajoDesdePartnerCommand,
    CrearTrabajoDesdePartnerHandler,
    CrearTrabajoHandler,
    IniciarSubTrabajoCommand,
    IniciarSubTrabajoHandler,
    RegistrarRediagnosticoCommand,
    RegistrarRediagnosticoHandler,
)
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
    SincronizarConPartnerHandler,
)
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker
from app.infraestructura.adaptadores.acl_partners import (
    CatalogoDePartnersEnMemoria,
    construir_catalogo,
)
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    LoggingMessageBroker,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajo_repository import (
    SqlAlchemyTrabajoRepository,
)
from app.infraestructura.configuracion import (
    MESSAGE_BROKER,
    PARTNER_CB_RECUPERACION_SEGUNDOS,
    PARTNER_CB_UMBRAL_FALLOS,
    PARTNER_SINCRONIZACION_ASINCRONA,
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
def obtener_catalogo_partners() -> CatalogoDePartnersEnMemoria:
    return construir_catalogo(
        asincrono=PARTNER_SINCRONIZACION_ASINCRONA,
        umbral_fallos=PARTNER_CB_UMBRAL_FALLOS,
        tiempo_recuperacion=PARTNER_CB_RECUPERACION_SEGUNDOS,
    )


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados, una vez por proceso."""

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    dispatcher.suscribir(DomainEvent, PublicarEventoDeIntegracionHandler(obtener_broker()))
    dispatcher.suscribir(DomainEvent, SincronizarConPartnerHandler(obtener_catalogo_partners()))
    return dispatcher


def handlers_de_comandos(session: Session) -> dict[type, Any]:
    """Casos de uso de escritura, con un repositorio atado a `session`."""

    repo = SqlAlchemyTrabajoRepository(session)
    dispatcher = obtener_dispatcher()
    crear = CrearTrabajoHandler(repo, dispatcher)
    return {
        CrearTrabajoCommand: crear,
        CrearTrabajoDesdePartnerCommand: CrearTrabajoDesdePartnerHandler(
            repo, obtener_catalogo_partners(), crear
        ),
        AsignarProveedorCommand: AsignarProveedorHandler(repo, dispatcher),
        IniciarSubTrabajoCommand: IniciarSubTrabajoHandler(repo, dispatcher),
        CompletarSubTrabajoCommand: CompletarSubTrabajoHandler(repo, dispatcher),
        RegistrarRediagnosticoCommand: RegistrarRediagnosticoHandler(repo, dispatcher),
        CancelarTrabajoCommand: CancelarTrabajoHandler(repo, dispatcher),
        CerrarTrabajoCommand: CerrarTrabajoHandler(repo, dispatcher),
    }


def reiniciar() -> None:
    """Detiene los hilos de sincronización, cierra el broker y limpia las cachés."""

    if obtener_catalogo_partners.cache_info().currsize:
        obtener_catalogo_partners().detener()
    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_catalogo_partners.cache_clear()
    obtener_broker.cache_clear()
