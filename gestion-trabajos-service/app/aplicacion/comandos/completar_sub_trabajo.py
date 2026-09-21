from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.trabajo import SubTrabajoId


@dataclass(frozen=True)
class CompletarSubTrabajoCommand:
    trabajo_id: str
    sub_trabajo_id: str
    evidencias: tuple[str, ...] = ()


class CompletarSubTrabajoHandler:
    def __init__(
        self,
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CompletarSubTrabajoCommand) -> TrabajoDTO:
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            trabajo.completar_sub_trabajo(SubTrabajoId(comando.sub_trabajo_id), comando.evidencias)
            # El sub-trabajo completado y el desbloqueo de sus dependientes se confirman juntos.
            uow.trabajos.guardar(trabajo)
            uow.confirmar()
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
