from dataclasses import dataclass

from .evento_de_trabajo import EventoDeTrabajo


@dataclass(frozen=True, kw_only=True)
class SubTrabajoCompletado(EventoDeTrabajo):
    sub_trabajo_id: str
    proveedor_id: str
    evidencias: tuple[str, ...]
