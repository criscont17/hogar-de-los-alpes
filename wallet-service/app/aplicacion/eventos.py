from app.aplicacion.puertos import DomainEventDispatcher
from app.seedwork.dominio import AggregateRoot


def despachar_eventos_pendientes(
    agregado: AggregateRoot, dispatcher: DomainEventDispatcher
) -> None:
    """Entrega al bus los eventos confirmados por el agregado.

    El caso de uso no decide qué ocurre con cada hecho: publicar hacia otros
    bounded contexts o registrar auditoría son responsabilidad de los handlers
    suscritos al dispatcher.
    """

    for evento in agregado.pull_domain_events():
        dispatcher.despachar(evento)
