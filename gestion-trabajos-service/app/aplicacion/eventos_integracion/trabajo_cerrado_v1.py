from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoCerradoV1(EventoDeIntegracionDeTrabajo):
    """Contrato que consume PagosBC (Conformist) para liberar el pago a cada proveedor."""

    costo_total: str
    moneda: str
    liquidaciones: tuple[dict[str, str], ...]
