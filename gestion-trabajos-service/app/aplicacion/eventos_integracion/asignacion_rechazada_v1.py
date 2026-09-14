from dataclasses import dataclass

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class AsignacionRechazadaV1(EventoDeIntegracionDeTrabajo):
    sub_trabajo_id: str
    proveedor_id: str
    monto_cotizado: str
    moneda: str
    motivo_rechazo: str
