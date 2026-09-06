from typing import Generic, TypeVar

TId = TypeVar("TId")


class Entity(Generic[TId]):
    """Entidad cuya igualdad está determinada por su identidad."""

    id: TId

    def __eq__(self, other: object) -> bool:
        return type(self) is type(other) and self.id == other.id  # type: ignore[attr-defined]

    def __hash__(self) -> int:
        return hash((type(self), self.id))
