"""Raíz de composición: decide qué adaptador concreto hay detrás de cada puerto.

La comparten las dos entradas del servicio (API REST y consumidor de comandos de
saga en Pulsar), por eso vive fuera de `entrada/api`. Las instancias sin estado se
cachean: el bus, el broker y el relay existen una sola vez por proceso, y
`reiniciar()` los libera al apagar. La unidad de trabajo no se cachea: se crea una
por petición HTTP o por mensaje, porque cada una abre y cierra su propia sesión de
base de datos.
"""

from functools import lru_cache

from app.aplicacion.comandos import ProcesadorComandosSagaWallet
from app.aplicacion.manejadores import AuditarEventoDeDominioHandler
from app.aplicacion.puertos import DomainEventDispatcher, MessageBroker, UnidadDeTrabajo
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    LoggingMessageBroker,
    PublicadorOutbox,
    PulsarMessageBroker,
)
from app.infraestructura.adaptadores.salida.persistencia.db import SessionLocal
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
from app.infraestructura.configuracion import (
    ACREDITACION_ESPERA_INICIAL_SEGUNDOS,
    ACREDITACION_FACTOR_BACKOFF,
    ACREDITACION_INTENTOS,
    MESSAGE_BROKER,
    OUTBOX_ESPERA_BASE_SEGUNDOS,
    OUTBOX_INTERVALO_SEGUNDOS,
    OUTBOX_LOTE,
    OUTBOX_MAX_INTENTOS,
    PULSAR_TOPICO_EVENTOS_INTEGRACION,
    PULSAR_URL,
)
from app.seedwork.dominio import DomainEvent
from app.seedwork.infraestructura import PoliticaDeReintentos


@lru_cache(maxsize=1)
def obtener_broker() -> MessageBroker:
    """Transporte detrás del puerto `MessageBroker`, según `MESSAGE_BROKER`.

    Solo lo usa el relay de la bandeja de salida: ningún caso de uso publica.
    """

    if MESSAGE_BROKER == "pulsar":
        return PulsarMessageBroker(PULSAR_URL, PULSAR_TOPICO_EVENTOS_INTEGRACION)
    return LoggingMessageBroker()


@lru_cache(maxsize=1)
def obtener_dispatcher() -> DomainEventDispatcher:
    """Construye el bus con sus suscriptores ya registrados.

    Desde que existe la bandeja de salida el bus solo atiende lógica interna —hoy,
    la auditoría—. El anuncio hacia otros bounded contexts salió de aquí a
    propósito: un suscriptor en memoria no puede prometer que el evento llegue.
    """

    dispatcher = InMemoryDomainEventDispatcher()
    dispatcher.suscribir(DomainEvent, AuditarEventoDeDominioHandler())
    return dispatcher


@lru_cache(maxsize=1)
def obtener_publicador_outbox() -> PublicadorOutbox:
    """Relay que vacía la bandeja de salida contra el broker configurado."""

    return PublicadorOutbox(
        fabrica_de_sesiones=SessionLocal,
        broker=obtener_broker(),
        intervalo_segundos=OUTBOX_INTERVALO_SEGUNDOS,
        lote=OUTBOX_LOTE,
        max_intentos=OUTBOX_MAX_INTENTOS,
        espera_base_segundos=OUTBOX_ESPERA_BASE_SEGUNDOS,
    )


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

    if obtener_broker.cache_info().currsize:
        obtener_broker().cerrar()
    obtener_dispatcher.cache_clear()
    obtener_broker.cache_clear()
    obtener_publicador_outbox.cache_clear()
    politica_de_reintentos.cache_clear()
    procesador_comandos_saga.cache_clear()
