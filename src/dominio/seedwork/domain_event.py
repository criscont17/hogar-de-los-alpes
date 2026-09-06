from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Evento inmutable ocurrido dentro del dominio."""

    occurred_at: datetime = field(default_factory=utc_now)
    event_id: UUID = field(default_factory=uuid4)

    @property
    def occurredAt(self) -> datetime:
        return self.occurred_at

    @property
    def eventId(self) -> UUID:
        return self.event_id
