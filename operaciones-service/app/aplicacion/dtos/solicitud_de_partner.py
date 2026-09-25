"""Modelo canónico de entrada: lo que cada adaptador extrae de la solicitud de su partner."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SubTrabajoSolicitado:
    clave: str
    categoria: str
    descripcion: str
    depende_de: tuple[str, ...] = ()


@dataclass(frozen=True)
class SolicitudDePartner:
    """Solicitud del partner traducida al vocabulario de HdA.

    Los datos del trabajo ya vienen en términos canónicos. Las reglas comerciales no: el
    adaptador solo indica qué niveles del acuerdo menciona la solicitud (`clave_sla`,
    `clave_tope`) y, si el partner autoriza un tope en la propia solicitud, cuál. El
    agregado `Partner` decide qué significan.
    """

    referencia_externa: str
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    sub_trabajos: tuple[SubTrabajoSolicitado, ...]
    clave_sla: str
    clave_tope: str | None = None
    tope_solicitado: Decimal | None = None
