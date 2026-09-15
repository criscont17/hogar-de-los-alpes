from dataclasses import dataclass
from typing import Any

from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo


@dataclass(frozen=True, kw_only=True)
class TrabajoCreadoV2(EventoDeIntegracionDeTrabajo):
    """Versión vigente.

    Frente a V1 agrupa la ubicación, expone el acuerdo (tope, SLA y su fecha
    límite) que Operaciones necesita para alertar SLAs en riesgo, y publica el
    flujo como grafo explícito (`depende_de` por sub-trabajo).
    """

    canal: str
    descripcion: str
    urgencia: str
    ubicacion: dict[str, str]
    acuerdo: dict[str, Any]
    flujo: tuple[dict[str, Any], ...]
