from dataclasses import dataclass

from app.dominio.errores import DatosDelTrabajoInvalidosError
from app.seedwork.dominio import ValueObject

from .enums import Categoria


@dataclass(frozen=True)
class SubTrabajoPlaneado(ValueObject):
    """Sub-trabajo tal como se solicita, antes de tener identidad.

    `clave` solo existe para expresar dependencias dentro de la misma solicitud;
    al crear el trabajo cada sub-trabajo recibe su propio identificador.
    """

    clave: str
    categoria: Categoria
    descripcion: str
    depende_de: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        clave = (self.clave or "").strip()
        if not clave:
            raise DatosDelTrabajoInvalidosError("Cada sub-trabajo requiere una clave")
        descripcion = (self.descripcion or "").strip()
        if not descripcion:
            raise DatosDelTrabajoInvalidosError(
                f"El sub-trabajo '{clave}' requiere una descripción"
            )
        dependencias = tuple(dict.fromkeys(dep.strip() for dep in self.depende_de if dep.strip()))
        object.__setattr__(self, "clave", clave)
        object.__setattr__(self, "descripcion", descripcion)
        object.__setattr__(self, "depende_de", dependencias)
