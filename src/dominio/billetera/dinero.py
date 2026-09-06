from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from dominio.errores import MonedaInvalidaError, MontoInvalidoError
from dominio.seedwork import ValueObject


@dataclass(frozen=True)
class Dinero(ValueObject):
    monto: Decimal
    moneda: str

    def __post_init__(self) -> None:
        try:
            monto = Decimal(str(self.monto))
        except (InvalidOperation, ValueError) as exc:
            raise MontoInvalidoError("El monto debe ser un número decimal válido") from exc
        if not monto.is_finite() or monto < 0:
            raise MontoInvalidoError("El monto no puede ser negativo ni infinito")
        moneda = self.moneda.strip().upper()
        if len(moneda) != 3 or not moneda.isalpha():
            raise MonedaInvalidaError("La moneda debe ser un código alfabético ISO de tres letras")
        object.__setattr__(self, "monto", monto)
        object.__setattr__(self, "moneda", moneda)

    def sumar(self, otro: "Dinero") -> "Dinero":
        self._validar_moneda(otro)
        return Dinero(self.monto + otro.monto, self.moneda)

    def restar(self, otro: "Dinero") -> "Dinero":
        self._validar_moneda(otro)
        return Dinero(self.monto - otro.monto, self.moneda)

    def es_mayor_que(self, otro: "Dinero") -> bool:
        self._validar_moneda(otro)
        return self.monto > otro.monto

    def _validar_moneda(self, otro: "Dinero") -> None:
        if self.moneda != otro.moneda:
            raise MonedaInvalidaError(
                f"No se pueden operar montos en {self.moneda} y {otro.moneda}"
            )
