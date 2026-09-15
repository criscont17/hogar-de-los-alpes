"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de eventos de
Pulsar). Las instancias se cachean: el bus, el broker y el catálogo de PSP
existen una sola vez por proceso, y `reiniciar()` los libera al apagar.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    CrearPagoCommand,
    CrearPagoHandler,
    ProcesarCierreDeTrabajoCommand,
    ProcesarCierreDeTrabajoHandler,
)
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
)
from app.aplicacion.puertos import CatalogoDePSP, DomainEventDispatcher, MessageBroker
from app.infraestructura.adaptadores.acl_psp import CatalogoDePSPEnMemoria, construir_catalogo_psp
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    LoggingMessageBroker,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_pago_repository import (
    SqlAlchemyPagoRepository,
)
from app.infraestructura.configuracion import (
    MESSAGE_BROKER,
    PSP_CB_RECUPERACION_SEGUNDOS,
    PSP_CB_UMBRAL_FALLOS,
    PULSAR_TOPICO_EVENTOS_PAGO,
    PULSAR_URL,
)
from app.seedwork.dominio import DomainEvent


@lru_cache(maxsize=1)
def obtener_broker() -> MessageBroker:
    """Adaptador de mensajería en uso según `MESSAGE_BROKER`."""

    if MESSAGE_BROKER == "pulsar":
        return PulsarMessageBroker(PULSAR_URL, PULSAR_TOPICO_EVENTOS_PAGO)
    if MESSAGE_BROKER == "memoria":
        return InMemoryMessageBroker()
    return LoggingMessageBroker()


@lru_cache(maxsize=1)
def obtener_catalogo_psp() -> CatalogoDePSP:
    return construir_catalogo_psp(
        umbral_fallos=PSP_CB_UMBRAL_FALLOS, tiempo_recuperacion=PSP_CB_RECUPERACION_SEGUNDOS
    )


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados, una vez por proceso."""

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    dispatcher.suscribir(DomainEvent, PublicarEventoDeIntegracionHandler(obtener_broker()))
    return dispatcher


def handlers_de_comandos(session: Session) -> dict[type, Any]:
    """Casos de uso de escritura, con un repositorio atado a `session`."""

    repo = SqlAlchemyPagoRepository(session)
    crear_pago = CrearPagoHandler(repo, obtener_dispatcher(), obtener_catalogo_psp())
    return {
        CrearPagoCommand: crear_pago,
        ProcesarCierreDeTrabajoCommand: ProcesarCierreDeTrabajoHandler(crear_pago),
    }


def reiniciar() -> None:
    """Cierra el broker y limpia las cachés."""

    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    obtener_catalogo_psp.cache_clear()
