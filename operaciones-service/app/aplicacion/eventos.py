from app.aplicacion.puertos import DomainEventDispatcher
from app.seedwork.dominio import AggregateRoot


def despachar_eventos_pendientes(
    agregado: AggregateRoot, dispatcher: DomainEventDispatcher
) -> None:
    """Entrega al bus los eventos confirmados por el agregado."""

    for evento in agregado.pull_domain_events():
        dispatcher.despachar(evento)
