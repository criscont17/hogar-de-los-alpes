from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoEnDisputaV1(EventoDeIntegracionDeTrabajo):
    """Aviso de que un trabajo ejecutado quedó pendiente de resolución manual.

    Lo consumen OperacionesBC (bandeja de revisión) y Marketplace. No implica
    reverso alguno: lo que falló fue la liquidación, no el servicio.
    """

    motivo: str
    estado_anterior: str
    liquidaciones_pendientes: tuple[dict[str, str], ...]
    moneda: str
