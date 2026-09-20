from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.errores import MontoMaximoExcedidoError, ProveedorNoPermitidoError
from app.dominio.trabajo import Dinero, SubTrabajoId


@dataclass(frozen=True)
class AsignarProveedorCommand:
    trabajo_id: str
    sub_trabajo_id: str
    proveedor_id: str
    monto_cotizado: Decimal


class AsignarProveedorHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: AsignarProveedorCommand) -> TrabajoDTO:
        rechazo: Exception | None = None
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            try:
                trabajo.asignar_proveedor(
                    SubTrabajoId(comando.sub_trabajo_id),
                    comando.proveedor_id,
                    Dinero(comando.monto_cotizado, trabajo.moneda),
                )
            except (ProveedorNoPermitidoError, MontoMaximoExcedidoError) as exc:
                # El rechazo no cambia el agregado: se revierte una transaccion vacia, pero
                # el hecho se anuncia igual porque el partner debe enterarse.
                rechazo = exc
            else:
                uow.trabajos.guardar(trabajo)
                uow.confirmar()
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        if rechazo is not None:
            raise rechazo
        return trabajo_a_dto(trabajo)
