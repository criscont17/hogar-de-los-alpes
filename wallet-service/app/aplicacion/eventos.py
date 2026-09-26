"""Qué se hace con los hechos que un agregado acaba de confirmar.

Son dos cosas distintas y ocurren en momentos distintos:

- **Encolarlos** en la bandeja de salida, *dentro* de la transacción, para que el
  anuncio hacia otros bounded contexts no pueda perderse ni contradecir al saldo.
- **Anunciarlos** al bus interno, *después* de confirmar, para la lógica que vive
  en este mismo proceso (hoy, la auditoría).

Antes de la bandeja de salida la publicación colgaba del bus y viajaba junto a la
auditoría; se separaron porque tienen garantías incompatibles: la auditoría puede
perderse sin consecuencias, el contrato público no.
"""

import logging

from app.aplicacion.manejadores.traductores import TRADUCTORES
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.seedwork.dominio import AggregateRoot, DomainEvent

logger = logging.getLogger("wallet.integration_events")


def encolar_eventos_pendientes(
    agregado: AggregateRoot, uow: UnidadDeTrabajo
) -> tuple[DomainEvent, ...]:
    """Traduce los hechos del agregado y los deja en la bandeja de salida.

    Se llama **antes** de `uow.confirmar()`, dentro del bloque: es lo que
    convierte «guardar el saldo» y «anunciar el movimiento» en una sola
    transacción. Devuelve los eventos de dominio drenados para que el caso de uso
    los anuncie al bus una vez confirmados.
    """

    hechos = agregado.pull_domain_events()
    for hecho in hechos:
        traductor = TRADUCTORES.get(type(hecho))
        if traductor is None:
            logger.warning(
                "evento de dominio sin traductor de integración: %s", type(hecho).__name__
            )
            continue
        evento = traductor(hecho)
        # Todos los contratos de WalletBC llevan la billetera: agrupa por ella para
        # que los movimientos de un mismo saldo lleguen en orden al consumidor.
        uow.eventos_salientes.encolar(evento, getattr(evento, "billetera_id", None))
    return hechos


def anunciar_hechos(
    hechos: tuple[DomainEvent, ...], dispatcher: DomainEventDispatcher
) -> None:
    """Entrega al bus interno los hechos ya confirmados en base."""

    for hecho in hechos:
        dispatcher.despachar(hecho)


def registrar_hechos(
    agregado: AggregateRoot, uow: UnidadDeTrabajo, dispatcher: DomainEventDispatcher
) -> None:
    """Encola y anuncia hechos que **no** acompañan un cambio de estado.

    Es el caso de los rechazos (`DebitoRechazado`, `AcreditacionRechazada`): el
    agregado no movió el saldo y su transacción se revirtió, pero el hecho
    ocurrió y hay que anunciarlo. Como no hay nada con lo que ser atómico, abre
    su propia transacción corta solo para la bandeja de salida.
    """

    if agregado is None:
        return
    with uow as unidad:
        hechos = encolar_eventos_pendientes(agregado, unidad)
        unidad.confirmar()
    anunciar_hechos(hechos, dispatcher)
