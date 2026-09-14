from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.errores import MontoMaximoExcedidoError, ProveedorNoPermitidoError
from app.dominio.trabajo import Dinero, SubTrabajoId
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class AsignarProveedorCommand:
    trabajo_id: str
    sub_trabajo_id: str
    proveedor_id: str
    monto_cotizado: Decimal


class AsignarProveedorHandler:
    def __init__(
        self,
        repo: TrabajoRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: AsignarProveedorCommand) -> TrabajoDTO:
        trabajo = cargar_trabajo(self._repo, comando.trabajo_id)
        try:
            trabajo.asignar_proveedor(
                SubTrabajoId(comando.sub_trabajo_id),
                comando.proveedor_id,
                Dinero(comando.monto_cotizado, trabajo.moneda),
            )
        except (ProveedorNoPermitidoError, MontoMaximoExcedidoError):
            # El rechazo no cambia el agregado, pero el partner debe enterarse.
            despachar_eventos_pendientes(trabajo, self._dispatcher)
            raise
        self._repo.guardar(trabajo)
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
