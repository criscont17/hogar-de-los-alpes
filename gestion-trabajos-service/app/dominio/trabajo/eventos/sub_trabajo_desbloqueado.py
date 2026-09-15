from dataclasses import dataclass

from .evento_de_trabajo import EventoDeTrabajo


@dataclass(frozen=True, kw_only=True)
class SubTrabajoDesbloqueado(EventoDeTrabajo):
    """Terminaron todas sus dependencias: puede publicarse o iniciarse."""

    sub_trabajo_id: str
    categoria: str
    estado: str
