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
    ProcesadorComandosSagaPago,
    ProcesarCierreDeTrabajoCommand,
    ProcesarCierreDeTrabajoHandler,
)
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
)
from app.aplicacion.puertos import (
    CatalogoDePSP,
    DomainEventDispatcher,
    MessageBroker,
    UnidadDeTrabajo,
)
from app.infraestructura.adaptadores.acl_psp import CatalogoDePSPEnMemoria, construir_catalogo_psp
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    LoggingMessageBroker,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
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


def unidad_de_trabajo() -> UnidadDeTrabajo:
    """Nueva unidad de trabajo: aquí se decide la tecnología de la transacción.

    Se crea una por petición HTTP o por mensaje de Pulsar, porque cada una abre y cierra
    su propia sesión de base de datos.
    """
    return SqlAlchemyUnidadDeTrabajo()


def handlers_de_comandos(uow: UnidadDeTrabajo) -> dict[type, Any]:
    """Casos de uso de escritura; `uow` delimita la transacción de cada uno."""

    crear_pago = CrearPagoHandler(uow, obtener_dispatcher(), obtener_catalogo_psp())
    return {
        CrearPagoCommand: crear_pago,
        ProcesarCierreDeTrabajoCommand: ProcesarCierreDeTrabajoHandler(crear_pago),
    }


def procesador_comandos_saga() -> ProcesadorComandosSagaPago:
    return ProcesadorComandosSagaPago(
        fabrica_uow=unidad_de_trabajo,
        dispatcher=obtener_dispatcher(),
        adaptadores=obtener_catalogo_psp(),
    )



def reiniciar() -> None:
    """Cierra el broker y limpia las cachés."""

    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    obtener_catalogo_psp.cache_clear()
