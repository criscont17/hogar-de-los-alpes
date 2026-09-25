from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class SubTrabajoDesbloqueadoV1(EventoDeIntegracionDeTrabajo):
    sub_trabajo_id: str
    categoria: str
    estado: str
