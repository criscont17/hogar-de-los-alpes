from dataclasses import dataclass
from datetime import datetime

from dominio.seedwork import Entity

from .dinero import Dinero
from .enums import MotivoMovimiento, TipoMovimiento
from .identificadores import MovimientoId


@dataclass(eq=False, frozen=True)
class Movimiento(Entity[MovimientoId]):
    """Registro histórico inmutable desde la perspectiva del agregado."""

    id: MovimientoId
    tipo: TipoMovimiento
    motivo: MotivoMovimiento
    monto: Dinero
    saldo_resultante: Dinero
    fecha: datetime
    referencia_externa: str | None = None
