from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    AsignarProveedorCommand,
    AsignarProveedorHandler,
    CancelarTrabajoCommand,
    CancelarTrabajoHandler,
    CerrarTrabajoCommand,
    CerrarTrabajoHandler,
    CompletarSubTrabajoCommand,
    CompletarSubTrabajoHandler,
    CrearTrabajoCommand,
    CrearTrabajoHandler,
    IniciarSubTrabajoCommand,
    IniciarSubTrabajoHandler,
    RegistrarRediagnosticoCommand,
    RegistrarRediagnosticoHandler,
)
from app.aplicacion.queries import ListarTrabajosHandler, ObtenerTrabajoHandler
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajo_repository import (
    SqlAlchemyTrabajoRepository,
)


def obtener_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyTrabajoRepository:
    return SqlAlchemyTrabajoRepository(session)


def obtener_handlers_de_comandos(
    session: Session = Depends(obtener_sesion),
) -> dict[type, Any]:
    # El cableado de comandos vive en el contenedor para que la API y el
    # consumidor de Pulsar ejecuten exactamente los mismos casos de uso.
    return contenedor.handlers_de_comandos(session)


def obtener_crear_handler(handlers=Depends(obtener_handlers_de_comandos)) -> CrearTrabajoHandler:
    return handlers[CrearTrabajoCommand]


def obtener_asignar_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> AsignarProveedorHandler:
    return handlers[AsignarProveedorCommand]


def obtener_iniciar_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> IniciarSubTrabajoHandler:
    return handlers[IniciarSubTrabajoCommand]


def obtener_completar_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> CompletarSubTrabajoHandler:
    return handlers[CompletarSubTrabajoCommand]


def obtener_rediagnostico_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> RegistrarRediagnosticoHandler:
    return handlers[RegistrarRediagnosticoCommand]


def obtener_cancelar_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> CancelarTrabajoHandler:
    return handlers[CancelarTrabajoCommand]


def obtener_cerrar_handler(handlers=Depends(obtener_handlers_de_comandos)) -> CerrarTrabajoHandler:
    return handlers[CerrarTrabajoCommand]


def obtener_trabajo_handler(repo=Depends(obtener_repo)) -> ObtenerTrabajoHandler:
    return ObtenerTrabajoHandler(repo)


def obtener_listar_handler(repo=Depends(obtener_repo)) -> ListarTrabajosHandler:
    return ListarTrabajosHandler(repo)
