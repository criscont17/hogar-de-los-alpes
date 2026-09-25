"""Piezas del modelo canónico con que cualquier canal pide crear un trabajo."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SubTrabajoSolicitado:
    clave: str
    categoria: str
    descripcion: str
    depende_de: tuple[str, ...] = ()


@dataclass(frozen=True)
class CondicionesDelAcuerdo:
    """Condiciones del acuerdo comercial ya resueltas a términos canónicos.

    Las resuelve OperacionesBC, dueño de los acuerdos con los partners. Marketplace no
    envía ninguna.
    """

    monto_maximo: Decimal | None = None
    proveedores_permitidos: frozenset[str] | None = None
    sla_horas: int | None = None
