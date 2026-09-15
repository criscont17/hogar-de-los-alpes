from .domain_event import DomainEvent
from .entity import Entity, TId


class AggregateRoot(Entity[TId]):
    """Raíz de agregado con una cola transitoria de eventos pendientes."""

    def __init__(self) -> None:
        super().__init__()
        self._domain_events: list[DomainEvent] = []

    def add_domain_event(self, event: DomainEvent) -> None:
        self._domain_events.append(event)

    def pull_domain_events(self) -> tuple[DomainEvent, ...]:
        events = tuple(self._domain_events)
        self._domain_events.clear()
        return events
