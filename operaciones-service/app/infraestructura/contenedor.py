"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten la API REST y el consumidor de eventos de Pulsar. Las instancias se cachean
una vez por proceso y `reiniciar()` las libera al apagar el servicio.
"""

from functools import lru_cache
from typing import Any

from app.aplicacion.comandos import (
    CrearTrabajoDesdePartnerCommand,
    CrearTrabajoDesdePartnerHandler,
    ProcesarEventoDeTrabajoCommand,
    ProcesarEventoDeTrabajoHandler,
    RegistrarPartnerCommand,
    RegistrarPartnerHandler,
)
from app.aplicacion.manejadores import AuditarEventoDeDominioHandler
from app.aplicacion.puertos import DomainEventDispatcher, GestionDeTrabajos, UnidadDeTrabajo
from app.infraestructura.adaptadores.acl_partners import (
    CatalogoDeAdaptadoresEnMemoria,
    construir_catalogo,
)
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.gestion_de_trabajos import (
    LoggingGestionDeTrabajos,
    PulsarGestionDeTrabajos,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
from app.infraestructura.configuracion import (
    MESSAGE_BROKER,
    PARTNER_CB_RECUPERACION_SEGUNDOS,
    PARTNER_CB_UMBRAL_FALLOS,
    PARTNER_SINCRONIZACION_ASINCRONA,
    PULSAR_TOPICO_COMANDOS_TRABAJO,
    PULSAR_URL,
)
from app.seedwork.dominio import DomainEvent


@lru_cache(maxsize=1)
def obtener_gestion_de_trabajos() -> GestionDeTrabajos:
    """Adaptador hacia GestionDeTrabajosBC según `MESSAGE_BROKER`."""

    if MESSAGE_BROKER == "pulsar":
        return PulsarGestionDeTrabajos(PULSAR_URL, PULSAR_TOPICO_COMANDOS_TRABAJO)
    return LoggingGestionDeTrabajos()


@lru_cache(maxsize=1)
def obtener_catalogo_adaptadores() -> CatalogoDeAdaptadoresEnMemoria:
    return construir_catalogo(
        asincrono=PARTNER_SINCRONIZACION_ASINCRONA,
        umbral_fallos=PARTNER_CB_UMBRAL_FALLOS,
        tiempo_recuperacion=PARTNER_CB_RECUPERACION_SEGUNDOS,
    )


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    return dispatcher


def unidad_de_trabajo() -> UnidadDeTrabajo:
    """Nueva unidad de trabajo: aqui se decide la tecnologia de la transaccion.

    Se crea una por peticion HTTP o por evento de Pulsar, porque cada una abre y cierra
    su propia sesion de base de datos con los dos repositorios encima.
    """

    return SqlAlchemyUnidadDeTrabajo()


def handlers_de_comandos(uow: UnidadDeTrabajo) -> dict[type, Any]:
    """Casos de uso de escritura; `uow` delimita la transaccion de cada uno."""

    adaptadores = obtener_catalogo_adaptadores()
    return {
        RegistrarPartnerCommand: RegistrarPartnerHandler(uow, adaptadores, obtener_dispatcher()),
        CrearTrabajoDesdePartnerCommand: CrearTrabajoDesdePartnerHandler(
            uow, adaptadores, obtener_gestion_de_trabajos()
        ),
        ProcesarEventoDeTrabajoCommand: ProcesarEventoDeTrabajoHandler(uow, adaptadores),
    }


def reiniciar() -> None:
    """Detiene los hilos de sincronización, cierra conexiones y limpia las cachés."""

    if obtener_catalogo_adaptadores.cache_info().currsize:
        obtener_catalogo_adaptadores().detener()
    if obtener_gestion_de_trabajos.cache_info().currsize:
        obtener_gestion_de_trabajos().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_catalogo_adaptadores.cache_clear()
    obtener_gestion_de_trabajos.cache_clear()
