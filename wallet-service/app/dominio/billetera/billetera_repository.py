from typing import Protocol

from .billetera import Billetera
from .identificadores import BilleteraId


class BilleteraRepository(Protocol):
    def guardar(self, billetera: Billetera) -> None: ...

    def obtener_por_id(self, id: BilleteraId) -> Billetera | None: ...

    def obtener_por_proveedor_id(self, proveedor_id: str) -> Billetera | None: ...
