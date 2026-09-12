from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import IntegrationEvent


class InMemoryMessageBroker(MessageBroker):
    """Adaptador para pruebas: acumula lo publicado en lugar de enviarlo."""

    def __init__(self) -> None:
        self._publicados: list[IntegrationEvent] = []

    @property
    def publicados(self) -> tuple[IntegrationEvent, ...]:
        return tuple(self._publicados)

    def publicar(self, evento: IntegrationEvent) -> None:
        self._publicados.append(evento)

    def limpiar(self) -> None:
        self._publicados.clear()
