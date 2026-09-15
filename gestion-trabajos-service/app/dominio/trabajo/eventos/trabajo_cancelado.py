from dataclasses import dataclass

from .evento_de_trabajo import EventoDeTrabajo, Liquidacion


@dataclass(frozen=True, kw_only=True)
class TrabajoCancelado(EventoDeTrabajo):
    """Cancelación con lo necesario para compensar: qué se alcanzó a completar
    (y debe pagarse) y qué quedó cancelado."""

    motivo: str
    sub_trabajos_cancelados: tuple[str, ...]
    liquidaciones: tuple[Liquidacion, ...]
    moneda: str
