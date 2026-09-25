from dataclasses import dataclass
from uuid import UUID, uuid4

from app.seedwork.dominio import ValueObject


@dataclass(frozen=True)
class TrabajoId(ValueObject):
    valor: UUID

    def __init__(self, valor: UUID | str):
        object.__setattr__(self, "valor", valor if isinstance(valor, UUID) else UUID(valor))

    @classmethod
    def nuevo(cls) -> "TrabajoId":
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True)
class SubTrabajoId(ValueObject):
    valor: UUID

    def __init__(self, valor: UUID | str):
        object.__setattr__(self, "valor", valor if isinstance(valor, UUID) else UUID(valor))

    @classmethod
    def nuevo(cls) -> "SubTrabajoId":
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.valor)
