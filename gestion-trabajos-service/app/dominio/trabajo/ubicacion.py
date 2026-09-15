from dataclasses import dataclass

from app.dominio.errores import DatosDelTrabajoInvalidosError
from app.seedwork.dominio import ValueObject


@dataclass(frozen=True)
class Ubicacion(ValueObject):
    """Predio donde se ejecuta el trabajo."""

    pais: str
    ciudad: str
    direccion: str

    def __post_init__(self) -> None:
        pais = (self.pais or "").strip().upper()
        if len(pais) != 2 or not pais.isalpha():
            raise DatosDelTrabajoInvalidosError("El país debe ser un código ISO alfa-2")
        ciudad = (self.ciudad or "").strip()
        if not ciudad:
            raise DatosDelTrabajoInvalidosError("La ciudad del predio es obligatoria")
        direccion = (self.direccion or "").strip()
        if not direccion:
            raise DatosDelTrabajoInvalidosError("La dirección del predio es obligatoria")
        object.__setattr__(self, "pais", pais)
        object.__setattr__(self, "ciudad", ciudad)
        object.__setattr__(self, "direccion", direccion)
