from dataclasses import dataclass

from app.dominio.errores import DatosDelTrabajoInvalidosError
from app.seedwork.dominio import ValueObject

from .enums import CanalDeOrigen


@dataclass(frozen=True)
class OrigenDelTrabajo(ValueObject):
    """Canal por el que entró el trabajo.

    Para un partner guarda su referencia propia (número de siniestro u orden) sin
    interpretarla: el dominio solo necesita poder devolverla cuando el partner
    pregunta por su trabajo o cuando se le notifica una novedad.
    """

    canal: CanalDeOrigen
    partner_id: str | None = None
    referencia_externa: str | None = None

    def __post_init__(self) -> None:
        partner_id = self.partner_id.strip() if self.partner_id else None
        referencia = self.referencia_externa.strip() if self.referencia_externa else None
        if self.canal is CanalDeOrigen.PARTNER:
            if not partner_id or not referencia:
                raise DatosDelTrabajoInvalidosError(
                    "Un trabajo de partner requiere partner_id y referencia externa"
                )
        elif partner_id:
            raise DatosDelTrabajoInvalidosError(
                "Solo los trabajos del canal Partner tienen partner_id"
            )
        object.__setattr__(self, "partner_id", partner_id)
        object.__setattr__(self, "referencia_externa", referencia)

    @classmethod
    def marketplace(cls) -> "OrigenDelTrabajo":
        return cls(CanalDeOrigen.MARKETPLACE)

    @classmethod
    def partner(cls, partner_id: str, referencia_externa: str) -> "OrigenDelTrabajo":
        return cls(CanalDeOrigen.PARTNER, partner_id, referencia_externa)
