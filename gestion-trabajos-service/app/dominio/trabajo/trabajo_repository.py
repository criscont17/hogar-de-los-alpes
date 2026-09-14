from typing import Protocol

from .enums import EstadoTrabajo
from .identificadores import TrabajoId
from .trabajo import Trabajo


class TrabajoRepository(Protocol):
    def guardar(self, trabajo: Trabajo) -> None: ...

    def obtener_por_id(self, id: TrabajoId) -> Trabajo | None: ...

    def obtener_por_referencia_de_partner(
        self, partner_id: str, referencia_externa: str
    ) -> Trabajo | None: ...

    def listar(
        self,
        estado: EstadoTrabajo | None = None,
        partner_id: str | None = None,
        limite: int = 50,
    ) -> list[Trabajo]: ...
