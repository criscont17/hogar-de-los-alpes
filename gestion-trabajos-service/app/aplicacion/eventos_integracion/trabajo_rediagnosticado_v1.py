from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoRediagnosticadoV1(EventoDeIntegracionDeTrabajo):
    hallazgo: str
    sub_trabajo_agregado_id: str
    categoria: str
    sub_trabajos_congelados: tuple[str, ...]
