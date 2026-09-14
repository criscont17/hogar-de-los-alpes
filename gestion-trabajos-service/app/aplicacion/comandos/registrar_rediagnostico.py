from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.trabajo import Categoria, SubTrabajoId
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class RegistrarRediagnosticoCommand:
    trabajo_id: str
    hallazgo: str
    categoria: str
    descripcion: str
    bloquea_a: tuple[str, ...] = ()


class RegistrarRediagnosticoHandler:
    def __init__(
        self,
        repo: TrabajoRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: RegistrarRediagnosticoCommand) -> TrabajoDTO:
        trabajo = cargar_trabajo(self._repo, comando.trabajo_id)
        trabajo.registrar_rediagnostico(
            hallazgo=comando.hallazgo,
            categoria=Categoria(comando.categoria),
            descripcion=comando.descripcion,
            bloquea_a=[SubTrabajoId(sub_id) for sub_id in comando.bloquea_a],
        )
        self._repo.guardar(trabajo)
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
