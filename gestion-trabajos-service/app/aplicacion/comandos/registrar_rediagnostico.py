from dataclasses import dataclass

from app.aplicacion.carga import cargar_trabajo
from app.aplicacion.dtos import TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import trabajo_a_dto
from app.aplicacion.puertos import DomainEventDispatcher, UnidadDeTrabajo
from app.dominio.trabajo import Categoria, SubTrabajoId


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
        uow: UnidadDeTrabajo,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
        self._dispatcher = dispatcher

    def ejecutar(self, comando: RegistrarRediagnosticoCommand) -> TrabajoDTO:
        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            # El sub-trabajo nuevo y el congelamiento de los dependientes son un solo cambio.
            trabajo.registrar_rediagnostico(
                hallazgo=comando.hallazgo,
                categoria=Categoria(comando.categoria),
                descripcion=comando.descripcion,
                bloquea_a=[SubTrabajoId(sub_id) for sub_id in comando.bloquea_a],
            )
            uow.trabajos.guardar(trabajo)
            uow.confirmar()
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
