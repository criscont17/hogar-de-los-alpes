from dataclasses import dataclass, field

from app.aplicacion.dtos import CondicionesDelAcuerdo, SubTrabajoSolicitado, TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import (
    acuerdo_desde_condiciones,
    plan_desde_solicitados,
    trabajo_a_dto,
)
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.trabajo import (
    CanalDeOrigen,
    OrigenDelTrabajo,
    TrabajoFactory,
    Ubicacion,
    Urgencia,
)
from app.dominio.trabajo.trabajo_repository import TrabajoRepository


@dataclass(frozen=True)
class CrearTrabajoCommand:
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    sub_trabajos: tuple[SubTrabajoSolicitado, ...]
    moneda: str = "COP"
    canal: str = CanalDeOrigen.MARKETPLACE.value
    partner_id: str | None = None
    referencia_externa: str | None = None
    condiciones: CondicionesDelAcuerdo = field(default_factory=CondicionesDelAcuerdo)


class CrearTrabajoHandler:
    def __init__(
        self,
        repo: TrabajoRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CrearTrabajoCommand) -> TrabajoDTO:
        trabajo = TrabajoFactory.crear(
            origen=OrigenDelTrabajo(
                CanalDeOrigen(comando.canal), comando.partner_id, comando.referencia_externa
            ),
            descripcion=comando.descripcion,
            urgencia=Urgencia(comando.urgencia),
            ubicacion=Ubicacion(comando.pais, comando.ciudad, comando.direccion),
            moneda=comando.moneda,
            acuerdo=acuerdo_desde_condiciones(comando.condiciones, comando.moneda),
            plan=plan_desde_solicitados(comando.sub_trabajos),
        )
        self._repo.guardar(trabajo)
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)
