"""Modelo canónico de entrada: lo que cualquier canal entrega para crear un trabajo.

Es el idioma común de la capa anti-corrupción. Cada partner envía su propio JSON,
SOAP o webhook; su adaptador siempre produce una `SolicitudDeTrabajo`, y el caso de
uso de creación no distingue de qué partner vino.
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class SubTrabajoSolicitado:
    clave: str
    categoria: str
    descripcion: str
    depende_de: tuple[str, ...] = ()


@dataclass(frozen=True)
class CondicionesDelAcuerdo:
    """Reglas del partner ya resueltas a términos canónicos."""

    monto_maximo: Decimal | None = None
    proveedores_permitidos: frozenset[str] | None = None
    sla_horas: int | None = None


@dataclass(frozen=True)
class SolicitudDeTrabajo:
    referencia_externa: str
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    sub_trabajos: tuple[SubTrabajoSolicitado, ...]
    condiciones: CondicionesDelAcuerdo = field(default_factory=CondicionesDelAcuerdo)
