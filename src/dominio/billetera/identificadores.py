from dataclasses import dataclass
from uuid import UUID, uuid4

from dominio.seedwork import ValueObject


@dataclass(frozen=True)
class BilleteraId(ValueObject):
    valor: UUID

    def __init__(self, valor: UUID | str):
        object.__setattr__(self, "valor", valor if isinstance(valor, UUID) else UUID(valor))

    @classmethod
    def nuevo(cls) -> "BilleteraId":
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.valor)


@dataclass(frozen=True)
class MovimientoId(ValueObject):
    valor: UUID

    def __init__(self, valor: UUID | str):
        object.__setattr__(self, "valor", valor if isinstance(valor, UUID) else UUID(valor))

    @classmethod
    def nuevo(cls) -> "MovimientoId":
        return cls(uuid4())

    def __str__(self) -> str:
        return str(self.valor)
