from dataclasses import dataclass

from .evento_de_trabajo import EventoDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoRediagnosticado(EventoDeTrabajo):
    """La naturaleza del trabajo cambió en plena ejecución.

    Ejemplo: quien llega a pintar una pared con moho descubre una tubería rota. Se
    agrega un sub-trabajo y los que dependen de él quedan congelados.
    """

    hallazgo: str
    sub_trabajo_agregado_id: str
    categoria: str
    sub_trabajos_congelados: tuple[str, ...]
