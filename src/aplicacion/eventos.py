from aplicacion.puertos import DomainEventDispatcher, EventPublisher
from dominio.billetera import Billetera


def despachar_eventos_pendientes(
    billetera: Billetera,
    dispatcher: DomainEventDispatcher,
    publisher: EventPublisher,
) -> None:
    """Despacha internamente y luego publica externamente cada evento confirmado."""

    for evento in billetera.pull_domain_events():
        dispatcher.despachar(evento)
        publisher.publicar(evento)
