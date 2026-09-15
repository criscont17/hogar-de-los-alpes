from collections.abc import Callable

from sqlalchemy.orm import Session

from app.aplicacion.comandos import ProcesarCierreDeTrabajoCommand
from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.salida.persistencia.db import SessionLocal


class EjecutorDeEventos:
    """Procesa un evento recibido por mensajería con una sesión de base de datos propia."""

    def __init__(self, fabrica_de_sesiones: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones

    def ejecutar(self, evento: EventoDeTrabajoRecibido) -> None:
        with self._fabrica_de_sesiones() as session:
            handler = contenedor.handlers_de_comandos(session)[ProcesarCierreDeTrabajoCommand]
            handler.ejecutar(ProcesarCierreDeTrabajoCommand(evento))
