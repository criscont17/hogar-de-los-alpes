from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.trabajo import SubTrabajoId


@dataclass(frozen=True)
class IniciarSubTrabajoCommand:
    trabajo_id: str
    sub_trabajo_id: str


class IniciarSubTrabajoHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: IniciarSubTrabajoCommand) -> TrabajoDTO:
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            trabajo.iniciar_sub_trabajo(SubTrabajoId(comando.sub_trabajo_id))
            uow.trabajos.guardar(trabajo)
            uow.confirmar()
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
