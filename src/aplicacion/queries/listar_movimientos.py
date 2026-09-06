from dataclasses import dataclass
from datetime import datetime, timezone

from aplicacion.dtos import MovimientoDTO
from aplicacion.mapeo import movimiento_a_dto
from dominio.billetera import BilleteraId, TipoMovimiento
from dominio.billetera.billetera_repository import BilleteraRepository
from dominio.errores import BilleteraNoEncontradaError


@dataclass(frozen=True)
class ListarMovimientosQuery:
    billetera_id: str
    fecha_desde: datetime | None = None
    fecha_hasta: datetime | None = None
    tipo: str | None = None


class ListarMovimientosHandler:
    def __init__(self, repo: BilleteraRepository) -> None:
        self._repo = repo

    def ejecutar(self, query: ListarMovimientosQuery) -> list[MovimientoDTO]:
        billetera = self._repo.obtener_por_id(BilleteraId(query.billetera_id))
        if billetera is None:
            raise BilleteraNoEncontradaError("La billetera no existe")
        tipo = TipoMovimiento(query.tipo) if query.tipo else None
        fecha_desde = self._normalizar_fecha(query.fecha_desde)
        fecha_hasta = self._normalizar_fecha(query.fecha_hasta)
        if fecha_desde is not None and fecha_hasta is not None and fecha_desde > fecha_hasta:
            raise ValueError("fecha_desde no puede ser posterior a fecha_hasta")
        movimientos = (
            movimiento
            for movimiento in billetera.movimientos
            if (fecha_desde is None or movimiento.fecha >= fecha_desde)
            and (fecha_hasta is None or movimiento.fecha <= fecha_hasta)
            and (tipo is None or movimiento.tipo is tipo)
        )
        return [movimiento_a_dto(item) for item in sorted(movimientos, key=lambda m: m.fecha)]

    @staticmethod
    def _normalizar_fecha(fecha: datetime | None) -> datetime | None:
        if fecha is None:
            return None
        return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)
