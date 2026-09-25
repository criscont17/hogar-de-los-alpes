import re
from dataclasses import dataclass

from app.dominio.errores import DatosDePartnerInvalidosError
from app.seedwork.dominio import ValueObject

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class PartnerId(ValueObject):
    """Identificador estable del partner dentro de HdA, en forma de slug (`seguros-alpes`).

    Es la misma referencia con la que GestionDeTrabajosBC etiqueta los trabajos del partner.
    """

    valor: str

    def __post_init__(self) -> None:
        valor = (self.valor or "").strip().lower()
        if len(valor) > 60 or not _SLUG.match(valor):
            raise DatosDePartnerInvalidosError(
                "El identificador del partner debe ser un slug en minúsculas, p. ej. seguros-alpes"
            )
        object.__setattr__(self, "valor", valor)

    def __str__(self) -> str:
        return self.valor
