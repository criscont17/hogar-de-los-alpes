from typing import Protocol

from .identificadores import PartnerId
from .partner import Partner


class PartnerRepository(Protocol):
    def guardar(self, partner: Partner) -> None: ...

    def obtener_por_id(self, id: PartnerId) -> Partner | None: ...

    def listar(self) -> list[Partner]: ...
