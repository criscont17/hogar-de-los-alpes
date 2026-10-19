from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import SobreDeEvento


class InMemoryMessageBroker(MessageBroker):
    """Adaptador para pruebas: acumula lo publicado en lugar de enviarlo.

    `fallar` simula un broker caído, que es el escenario para el que existe la
    bandeja de salida: con él encendido, el relay no puede marcar nada como
    publicado y los eventos deben quedarse esperando en la base.
    """

    def __init__(self) -> None:
        self._publicados: list[SobreDeEvento] = []
        self.fallar = False

    @property
    def publicados(self) -> tuple[SobreDeEvento, ...]:
        return tuple(self._publicados)

    def publicar(self, sobre: SobreDeEvento) -> None:
        if self.fallar:
            raise ConnectionError("broker no disponible (simulación)")
        self._publicados.append(sobre)

    def limpiar(self) -> None:
        self._publicados.clear()
