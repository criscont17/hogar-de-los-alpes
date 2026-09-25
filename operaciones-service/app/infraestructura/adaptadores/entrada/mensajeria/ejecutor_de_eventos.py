from collections.abc import Callable

from app.aplicacion.comandos import ProcesarEventoDeTrabajoCommand
from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.aplicacion.puertos import UnidadDeTrabajo
from app.infraestructura import contenedor


class EjecutorDeEventos:
    """Procesa un evento recibido por mensajeria en su propia unidad de trabajo."""

    def __init__(
        self,
        fabrica_de_unidades: Callable[[], UnidadDeTrabajo] = contenedor.unidad_de_trabajo,
    ) -> None:
        self._fabrica_de_unidades = fabrica_de_unidades

    def ejecutar(self, evento: EventoDeTrabajoRecibido) -> None:
        handlers = contenedor.handlers_de_comandos(self._fabrica_de_unidades())
        handlers[ProcesarEventoDeTrabajoCommand].ejecutar(ProcesarEventoDeTrabajoCommand(evento))
