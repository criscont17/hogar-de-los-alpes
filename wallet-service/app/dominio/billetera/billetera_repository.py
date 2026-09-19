from typing import Protocol

from .billetera import Billetera
from .enums import EstadoBilletera
from .identificadores import BilleteraId


class BilleteraRepository(Protocol):
    def guardar(self, billetera: Billetera) -> None: ...

    def obtener_por_id(self, id: BilleteraId) -> Billetera | None: ...

    def obtener_por_proveedor_id(self, proveedor_id: str) -> Billetera | None: ...

    def eliminar(self, billetera: Billetera) -> None: ...

    def listar(
        self,
        estado: EstadoBilletera | None = None,
        proveedor_id: str | None = None,
        limite: int = 50,
        desplazamiento: int = 0,
    ) -> list[Billetera]: ...

    def contar(
        self,
        estado: EstadoBilletera | None = None,
        proveedor_id: str | None = None,
    ) -> int: ...
