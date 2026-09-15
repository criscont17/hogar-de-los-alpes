from dataclasses import dataclass, field

from app.aplicacion.dtos import CondicionesDelAcuerdo, SubTrabajoSolicitado, TrabajoDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import (
    condiciones_desde_dto,
    plan_desde_solicitados,
    trabajo_a_dto,
)
from app.aplicacion.puertos import DomainEventDispatcher
from app.dominio.errores import TrabajoDuplicadoError
from app.dominio.trabajo import (
    CanalDeOrigen,
    OrigenDelTrabajo,
    Trabajo,
    TrabajoFactory,
    Ubicacion,
    Urgencia,
)
from app.dominio.trabajo.eventos import CreacionDeTrabajoRechazada
from app.dominio.trabajo.trabajo_repository import TrabajoRepository
from app.seedwork.dominio import DomainError


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
    """Crea un trabajo, venga de Marketplace o de un partner a través de OperacionesBC.

    - Para un partner es idempotente: la misma referencia devuelve el trabajo existente,
      así OperacionesBC y Pulsar pueden reintentar sin duplicar.
    - Si la solicitud no forma un trabajo válido (por ejemplo, dependencias en ciclo),
      publica `CreacionDeTrabajoRechazada` antes de propagar el error: quien envió el
      comando por mensajería no recibe la excepción y necesita enterarse.
    """

    def __init__(
        self,
        repo: TrabajoRepository,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._dispatcher = dispatcher

    def ejecutar(self, comando: CrearTrabajoCommand) -> TrabajoDTO:
        existente = self._existente(comando)
        if existente is not None:
            return trabajo_a_dto(existente)

        try:
            trabajo = TrabajoFactory.crear(
                origen=OrigenDelTrabajo(
                    CanalDeOrigen(comando.canal), comando.partner_id, comando.referencia_externa
                ),
                descripcion=comando.descripcion,
                urgencia=Urgencia(comando.urgencia),
                ubicacion=Ubicacion(comando.pais, comando.ciudad, comando.direccion),
                moneda=comando.moneda,
                condiciones=condiciones_desde_dto(comando.condiciones, comando.moneda),
                plan=plan_desde_solicitados(comando.sub_trabajos),
            )
        except (DomainError, ValueError) as exc:
            self._dispatcher.despachar(
                CreacionDeTrabajoRechazada(
                    canal=comando.canal,
                    partner_id=comando.partner_id,
                    referencia_externa=comando.referencia_externa,
                    motivo=str(exc),
                )
            )
            raise

        try:
            self._repo.guardar(trabajo)
        except TrabajoDuplicadoError:
            # Dos entregas simultáneas del mismo comando: otra ganó la carrera.
            existente = self._existente(comando)
            if existente is None:
                raise
            return trabajo_a_dto(existente)
        despachar_eventos_pendientes(trabajo, self._dispatcher)
        return trabajo_a_dto(trabajo)

    def _existente(self, comando: CrearTrabajoCommand) -> Trabajo | None:
        if not comando.partner_id or not comando.referencia_externa:
            return None
        return self._repo.obtener_por_referencia_de_partner(
            comando.partner_id, comando.referencia_externa
        )
