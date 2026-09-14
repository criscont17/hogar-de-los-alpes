from dataclasses import dataclass

from app.dominio.errores import DatosDelTrabajoInvalidosError
from app.seedwork.dominio import ValueObject

from .dinero import Dinero


@dataclass(frozen=True)
class AcuerdoComercial(ValueObject):
    """Condiciones que el trabajo debe respetar, expresadas en términos canónicos.

    Es una fotografía tomada al crear el trabajo: si el partner cambia sus reglas
    después, los trabajos en curso conservan las vigentes cuando se crearon.

    El dominio no sabe de planes de póliza, niveles de urgencia de un banco ni
    tarifas de un comercio. La capa anti-corrupción traduce esas particularidades
    a estos tres valores, y por eso un partner nuevo no obliga a cambiar el agregado.
    """

    monto_maximo: Dinero | None = None
    proveedores_permitidos: frozenset[str] | None = None
    sla_horas: int | None = None

    def __post_init__(self) -> None:
        if self.monto_maximo is not None and self.monto_maximo.monto <= 0:
            raise DatosDelTrabajoInvalidosError(
                "El monto máximo del acuerdo debe ser mayor que cero"
            )
        if self.proveedores_permitidos is not None:
            red = frozenset(
                proveedor.strip()
                for proveedor in self.proveedores_permitidos
                if proveedor and proveedor.strip()
            )
            if not red:
                raise DatosDelTrabajoInvalidosError(
                    "La red de proveedores del acuerdo no puede estar vacía"
                )
            object.__setattr__(self, "proveedores_permitidos", red)
        if self.sla_horas is not None and self.sla_horas <= 0:
            raise DatosDelTrabajoInvalidosError(
                "El SLA del acuerdo debe ser un número positivo de horas"
            )

    @classmethod
    def abierto(cls) -> "AcuerdoComercial":
        """Sin tope ni red restringida: el caso de Marketplace."""
        return cls()

    def admite_proveedor(self, proveedor_id: str) -> bool:
        return self.proveedores_permitidos is None or proveedor_id in self.proveedores_permitidos

    def admite_costo(self, costo: Dinero) -> bool:
        return self.monto_maximo is None or not costo.es_mayor_que(self.monto_maximo)
