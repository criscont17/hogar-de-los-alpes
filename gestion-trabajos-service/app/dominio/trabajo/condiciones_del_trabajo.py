from dataclasses import dataclass

from app.dominio.errores import DatosDelTrabajoInvalidosError
from app.seedwork.dominio import ValueObject

from .dinero import Dinero


@dataclass(frozen=True)
class CondicionesDelTrabajo(ValueObject):
    """Condiciones que el trabajo debe respetar, expresadas en términos canónicos.

    Para los trabajos de partners llegan ya resueltas desde OperacionesBC, dueño de los
    acuerdos comerciales. Son una fotografía tomada al crear el trabajo: si el partner
    renegocia después, los trabajos en curso conservan las condiciones con que se crearon.

    GestionDeTrabajosBC no sabe de planes de póliza, niveles de un banco ni tarifas de un
    comercio, y por eso integrar un partner nuevo no obliga a cambiar el agregado.
    """

    monto_maximo: Dinero | None = None
    proveedores_permitidos: frozenset[str] | None = None
    sla_horas: int | None = None

    def __post_init__(self) -> None:
        if self.monto_maximo is not None and self.monto_maximo.monto <= 0:
            raise DatosDelTrabajoInvalidosError("El monto máximo del trabajo debe ser mayor que cero")
        if self.proveedores_permitidos is not None:
            red = frozenset(
                proveedor.strip()
                for proveedor in self.proveedores_permitidos
                if proveedor and proveedor.strip()
            )
            if not red:
                raise DatosDelTrabajoInvalidosError(
                    "La red de proveedores permitidos no puede estar vacía"
                )
            object.__setattr__(self, "proveedores_permitidos", red)
        if self.sla_horas is not None and self.sla_horas <= 0:
            raise DatosDelTrabajoInvalidosError("El SLA debe ser un número positivo de horas")

    @classmethod
    def sin_restricciones(cls) -> "CondicionesDelTrabajo":
        """Sin tope ni red restringida: el caso de Marketplace."""
        return cls()

    def admite_proveedor(self, proveedor_id: str) -> bool:
        return self.proveedores_permitidos is None or proveedor_id in self.proveedores_permitidos

    def admite_costo(self, costo: Dinero) -> bool:
        return self.monto_maximo is None or not costo.es_mayor_que(self.monto_maximo)
