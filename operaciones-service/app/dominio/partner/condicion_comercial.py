from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.dominio.errores import AcuerdoInvalidoError
from app.seedwork.dominio import ValueObject

from .enums import TipoCondicion


@dataclass(frozen=True)
class CondicionComercial(ValueObject):
    """Cláusula del acuerdo comercial.

    Para un nivel que el partner reconoce (plan de póliza, prioridad, país, tipo de orden)
    fija un tope de costo o un SLA en horas. La `clave` es el nombre que usa el partner, así
    que el acuerdo habla su idioma y los adaptadores no necesitan conocer las reglas.
    """

    tipo: TipoCondicion
    clave: str
    valor: Decimal

    def __post_init__(self) -> None:
        clave = (self.clave or "").strip().upper()
        if not clave:
            raise AcuerdoInvalidoError("Cada condición del acuerdo requiere una clave")
        try:
            valor = Decimal(str(self.valor))
        except (InvalidOperation, ValueError) as exc:
            raise AcuerdoInvalidoError(f"La condición '{clave}' tiene un valor inválido") from exc
        if not valor.is_finite() or valor <= 0:
            raise AcuerdoInvalidoError(f"La condición '{clave}' debe tener un valor positivo")
        if self.tipo is TipoCondicion.SLA and valor != valor.to_integral_value():
            raise AcuerdoInvalidoError(f"El SLA '{clave}' debe expresarse en horas enteras")
        object.__setattr__(self, "clave", clave)
        object.__setattr__(self, "valor", valor)
