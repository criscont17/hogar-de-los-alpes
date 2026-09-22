"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de comandos de
saga en Pulsar), por eso vive fuera de `entrada/api`. Las instancias sin estado se
cachean: el bus y el broker existen una sola vez por proceso, y `reiniciar()` los
libera al apagar. La unidad de trabajo no se cachea: se crea una por petición HTTP
o por mensaje, porque cada una abre y cierra su propia sesión de base de datos.
"""

from functools import lru_cache

from app.aplicacion.comandos import ProcesadorComandosSagaWallet
from app.aplicacion.manejadores import (
    AuditarEventoDeDominioHandler,
    PublicarEventoDeIntegracionHandler,
)
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker, UnidadDeTrabajo
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import LoggingMessageBroker
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
from app.infraestructura.configuracion import (
    ACREDITACION_ESPERA_INICIAL_SEGUNDOS,
    ACREDITACION_FACTOR_BACKOFF,
    ACREDITACION_INTENTOS,
)
from app.seedwork.dominio import DomainEvent
from app.seedwork.infraestructura import PoliticaDeReintentos


@lru_cache(maxsize=1)
def obtener_broker() -> MessageBroker:
    """Adaptador de mensajería en uso. Cambiar aquí para migrar a Pulsar, Rabbit o SQS."""

    return LoggingMessageBroker()


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados.

    Al estar cacheado, el registro ocurre una sola vez por proceso sin necesidad
    de banderas externas, y cada test puede pedir un bus limpio con `cache_clear()`.
    """

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    dispatcher.suscribir(DomainEvent, PublicarEventoDeIntegracionHandler(obtener_broker()))
    return dispatcher


def unidad_de_trabajo() -> UnidadDeTrabajo:
    """Nueva unidad de trabajo: aquí se decide la tecnología de la transacción."""

    return SqlAlchemyUnidadDeTrabajo()


@lru_cache(maxsize=1)
def politica_de_reintentos() -> PoliticaDeReintentos:
    return PoliticaDeReintentos(
        intentos=ACREDITACION_INTENTOS,
        espera_inicial=ACREDITACION_ESPERA_INICIAL_SEGUNDOS,
        factor=ACREDITACION_FACTOR_BACKOFF,
    )


@lru_cache(maxsize=1)
def procesador_comandos_saga() -> ProcesadorComandosSagaWallet:
    return ProcesadorComandosSagaWallet(
        fabrica_uow=unidad_de_trabajo,
        dispatcher=obtener_dispatcher(),
        politica=politica_de_reintentos(),
    )


def reiniciar() -> None:
    """Limpia las cachés del proceso (apagado del servicio y aislamiento de pruebas)."""

    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    politica_de_reintentos.cache_clear()
    procesador_comandos_saga.cache_clear()
