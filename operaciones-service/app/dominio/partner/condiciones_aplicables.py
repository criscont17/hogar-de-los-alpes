from dataclasses import dataclass
from decimal import Decimal

from app.seedwork.dominio import ValueObject


@dataclass(frozen=True)
class CondicionesAplicables(ValueObject):
    """Lo que un trabajo debe respetar según el acuerdo vigente al momento de solicitarlo.

    Es lo único del acuerdo que viaja a GestionDeTrabajosBC: tres valores canónicos, sin
    planes, niveles ni claves propias del partner.
    """

    monto_maximo: Decimal | None
    proveedores_permitidos: frozenset[str] | None
    sla_horas: int
