from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class EstadoTrabajoDePartner(str, Enum):
    SOLICITADO = "Solicitado"
    CREADO = "Creado"
    EN_EJECUCION = "EnEjecucion"
    CERRADO = "Cerrado"
    CANCELADO = "Cancelado"
    RECHAZADO = "Rechazado"


@dataclass(frozen=True)
class SubTrabajoDePartnerDTO:
    id: str
    categoria: str
    estado: str
    proveedor_id: str | None = None
    monto_cotizado: Decimal | None = None


@dataclass(frozen=True)
class TrabajoDePartnerDTO:
    """Vista que OperacionesBC mantiene de cada trabajo de un partner.

    Se alimenta de los eventos que publica GestionDeTrabajosBC, así que es consistente en
    forma eventual: justo después de la solicitud el trabajo aparece `Solicitado` y sin
    `trabajo_id`, hasta que llega `TrabajoCreadoV2`.
    """

    partner_id: str
    referencia_externa: str
    estado: EstadoTrabajoDePartner
    fecha_solicitud: datetime
    trabajo_id: str | None = None
    moneda: str | None = None
    monto_maximo: Decimal | None = None
    sla_horas: int | None = None
    costo_total: Decimal = Decimal("0")
    motivo_rechazo: str | None = None
    sub_trabajos: tuple[SubTrabajoDePartnerDTO, ...] = ()
