from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EventoDeTrabajoRecibido:
    """Hecho publicado por GestionDeTrabajosBC, tal como llega por la plataforma de mensajería.

    PagosBC es Conformist con este contrato (mapa de contextos TO-BE): no lo traduce
    ni lo envuelve en una capa anti-corrupción, lo consume tal cual porque GestionDeTrabajosBC
    es upstream estable. Solo `TrabajoCerradoV1` le interesa; el resto se descarta sin abrir
    el cuerpo del mensaje.
    """

    nombre: str
    datos: Mapping[str, Any]

    @property
    def trabajo_id(self) -> str:
        return str(self.datos["trabajo_id"])

    @property
    def costo_total(self) -> str:
        return str(self.datos["costo_total"])

    @property
    def moneda(self) -> str:
        return str(self.datos["moneda"])

    @property
    def liquidaciones(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(self.datos.get("liquidaciones", ()))
