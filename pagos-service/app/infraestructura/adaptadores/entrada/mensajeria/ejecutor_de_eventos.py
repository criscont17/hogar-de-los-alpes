from collections.abc import Callable

from app.aplicacion.comandos import ProcesarCierreDeTrabajoCommand
from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.aplicacion.puertos import UnidadDeTrabajo
from app.infraestructura import contenedor


class EjecutorDeEventos:
    """Procesa un evento recibido por mensajería en su propia unidad de trabajo."""

    def __init__(
        self,
        fabrica_de_unidades: Callable[[], UnidadDeTrabajo] = contenedor.unidad_de_trabajo,
    ) -> None:
        self._fabrica_de_unidades = fabrica_de_unidades

    def ejecutar(self, evento: EventoDeTrabajoRecibido) -> None:
        handler = contenedor.handlers_de_comandos(self._fabrica_de_unidades())[
            ProcesarCierreDeTrabajoCommand
        ]
        handler.ejecutar(ProcesarCierreDeTrabajoCommand(evento))

