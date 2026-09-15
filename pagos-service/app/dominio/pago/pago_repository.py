from abc import ABC, abstractmethod

from .identificadores import PagoId
from .pago import Pago


class PagoRepository(ABC):
    """Puerto de salida hacia la persistencia del agregado `Pago`."""

    @abstractmethod
    def guardar(self, pago: Pago) -> None:
        """Inserta o actualiza. Lanza `PagoDuplicadoError` si la referencia
        externa ya existe en otro pago (idempotencia)."""

    @abstractmethod
    def obtener_por_id(self, id: PagoId) -> Pago | None: ...

    @abstractmethod
    def obtener_por_referencia_externa(self, referencia_externa: str) -> Pago | None: ...

    @abstractmethod
    def listar(self, trabajo_id: str | None = None, limite: int = 50) -> list[Pago]: ...
