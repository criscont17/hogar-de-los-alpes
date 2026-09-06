from .entity import Entity
from .domain_event import DomainEvent


class AggregateRoot(Entity):
    """Raíz de agregado con una cola transitoria de eventos pendientes."""

    def __init__(self) -> None:
        self._domain_events: list[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pull_domain_events(self) -> tuple[DomainEvent, ...]:
        events = tuple(self._domain_events)
        self._domain_events.clear()
        return events

    # Alias solicitados en el enunciado, sin perder el estilo Python del dominio.
    def addDomainEvent(self, event: DomainEvent) -> None:
        self.add_domain_event(event)

    def pullDomainEvents(self) -> tuple[DomainEvent, ...]:
        return self.pull_domain_events()
