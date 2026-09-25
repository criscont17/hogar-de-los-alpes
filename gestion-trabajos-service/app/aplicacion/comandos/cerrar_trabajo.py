from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo


@dataclass(frozen=True)
class CerrarTrabajoCommand:
    trabajo_id: str


class CerrarTrabajoHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CerrarTrabajoCommand) -> TrabajoDTO:
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            trabajo.cerrar()
            uow.trabajos.guardar(trabajo)
            uow.confirmar()
        # Fuera de la transaccion: los eventos se anuncian cuando el hecho ya es definitivo.
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
