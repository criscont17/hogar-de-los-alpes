from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo


@dataclass(frozen=True)
class CancelarTrabajoCommand:
    trabajo_id: str
    motivo: str


class CancelarTrabajoHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CancelarTrabajoCommand) -> TrabajoDTO:
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            trabajo.cancelar(comando.motivo)
            uow.trabajos.guardar(trabajo)
            uow.confirmar()
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
