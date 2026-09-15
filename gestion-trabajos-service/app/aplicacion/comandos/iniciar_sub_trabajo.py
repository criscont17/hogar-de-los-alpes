from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.trabajo import SubTrabajoId
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class IniciarSubTrabajoCommand:
    trabajo_id: str
    sub_trabajo_id: str


class IniciarSubTrabajoHandler:
    def __init__(
        self,
        repo: TrabajoRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: IniciarSubTrabajoCommand) -> TrabajoDTO:
        trabajo = cargar_trabajo(self._repo, comando.trabajo_id)
        trabajo.iniciar_sub_trabajo(SubTrabajoId(comando.sub_trabajo_id))
        self._repo.guardar(trabajo)
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
