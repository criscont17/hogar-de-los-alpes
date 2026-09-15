from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.dominio.errores import MonedaInvalidaError, MontoInvalidoError
from app.seedwork.dominio import ValueObject


@dataclass(frozen=True)
class Dinero(ValueObject):
    """Monto en una moneda ISO. La operación con varios PSPs y países impide
    tratar montos de monedas distintas como si fueran comparables."""

    monto: Decimal
    moneda: str

    def __post_init__(self) -> None:
        try:
            monto = Decimal(str(self.monto))
        except (InvalidOperation, ValueError) as exc:
            raise MontoInvalidoError("El monto debe ser un número decimal válido") from exc
        if not monto.is_finite() or monto <= 0:
            raise MontoInvalidoError("El monto debe ser positivo y finito")
        moneda = (self.moneda or "").strip().upper()
        if len(moneda) != 3 or not moneda.isalpha():
            raise MonedaInvalidaError("La moneda debe ser un código alfabético ISO de tres letras")
        object.__setattr__(self, "monto", monto)
        object.__setattr__(self, "moneda", moneda)
