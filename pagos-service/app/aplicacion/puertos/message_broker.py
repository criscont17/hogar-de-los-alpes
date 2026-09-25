from abc import ABC, abstractmethod

from app.seedwork.aplicacion import IntegrationEvent


class MessageBroker(ABC):
    """Puerto de salida hacia la plataforma de mensajería.

    Es la interfaz que se inyecta al handler que traduce eventos de dominio en
    eventos de integración. Los adaptadores concretos (Apache Pulsar o el de logs
    para desarrollo) viven en infraestructura y se sustituyen sin tocar dominio
    ni aplicación.
    """

    @abstractmethod
    def publicar(self, evento: IntegrationEvent) -> None:
        """Entrega el evento al transporte subyacente."""

    def cerrar(self) -> None:
        """Libera conexiones al apagar el servicio. Por defecto no hay nada que liberar."""
