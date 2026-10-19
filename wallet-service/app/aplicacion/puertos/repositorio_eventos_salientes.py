from abc import ABC, abstractmethod

from app.seedwork.aplicacion import IntegrationEvent


class RepositorioEventosSalientes(ABC):
    """Puerto de la bandeja de salida (*outbox*), escrito dentro de la transacción.

    El caso de uso encola aquí el evento de integración **antes** de confirmar,
    de modo que el hecho y su anuncio se guardan con el mismo `commit`: o quedan
    los dos o no queda ninguno. Publicarlo es problema posterior del relay, que
    corre fuera de la transacción y puede reintentar sin arriesgar el saldo.

    Se obtiene de la unidad de trabajo, igual que el repositorio de billeteras,
    porque esa es la garantía de que ambos comparten sesión.
    """

    @abstractmethod
    def encolar(self, evento: IntegrationEvent, clave_particion: str | None = None) -> None:
        """Deja el evento pendiente de publicación en la misma sesión del caso de uso."""
