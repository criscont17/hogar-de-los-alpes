from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoCanceladoV1(EventoDeIntegracionDeTrabajo):
    motivo: str
    sub_trabajos_cancelados: tuple[str, ...]
    liquidaciones: tuple[dict[str, str], ...]
    moneda: str
