from collections import defaultdict
from collections.abc import Callable

from dominio.seedwork import DomainEvent

DomainEventHandler = Callable[[DomainEvent], None]


class InMemoryDomainEventDispatcher:
    """Bus interno síncrono, reemplazable sin cambiar los casos de uso."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[DomainEventHandler]] = defaultdict(list)

    def registrar(self, event_type: type[DomainEvent], handler: DomainEventHandler) -> None:
        self._handlers[event_type].append(handler)

    def despachar(self, evento: DomainEvent) -> None:
        for handler in self._handlers[type(evento)]:
            handler(evento)
