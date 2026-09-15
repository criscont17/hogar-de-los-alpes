from app.aplicacion.puertos import DomainEventDispatcher
from app.seedwork.dominio import AggregateRoot


def despachar_eventos_pendientes(
    agregado: AggregateRoot, dispatcher: DomainEventDispatcher
) -> None:
    """Entrega al bus los eventos confirmados por el agregado.

    El caso de uso no decide qué ocurre con cada hecho: publicarlo hacia otros
    bounded contexts (WalletBC, por ejemplo) o auditarlo es responsabilidad de
    los handlers suscritos al dispatcher.
    """

    for evento in agregado.pull_domain_events():
        dispatcher.despachar(evento)
