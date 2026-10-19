from abc import ABC, abstractmethod

from app.seedwork.aplicacion import SobreDeEvento


class MessageBroker(ABC):
    """Puerto de salida hacia la plataforma de mensajería.

    Su único cliente es el relay de la bandeja de salida: los casos de uso ya no
    publican, encolan. Por eso recibe un `SobreDeEvento` —contrato ya
    serializado— y no un objeto de aplicación.

    `publicar` debe ser **síncrono**: el relay solo marca una fila como publicada
    cuando este método retorna sin excepción, así que un envío que no espera la
    confirmación del broker haría perder eventos justamente en el caso que el
    patrón existe para cubrir. Los adaptadores concretos (Pulsar, el de logs o el
    de memoria para pruebas) viven en infraestructura.
    """

    @abstractmethod
    def publicar(self, sobre: SobreDeEvento) -> None:
        """Entrega el sobre al transporte. Lanza si la entrega no se confirmó."""

    def cerrar(self) -> None:
        """Libera los recursos del transporte. Por defecto no hay nada que cerrar."""
