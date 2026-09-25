from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from app.seedwork.dominio import DomainEvent

E = TypeVar("E", bound=DomainEvent)


class DomainEventHandler(ABC, Generic[E]):
    """Suscriptor de un evento de dominio.

    Cada implementación reacciona a un hecho ya ocurrido: registrar auditoría,
    traducirlo a un evento de integración, disparar otro caso de uso. El handler
    no conoce quién lo invoca ni con qué transporte se publica lo que produce.
    """

    @abstractmethod
    def manejar(self, evento: E) -> None:
        """Procesa el evento. Debe ser idempotente siempre que sea posible."""
