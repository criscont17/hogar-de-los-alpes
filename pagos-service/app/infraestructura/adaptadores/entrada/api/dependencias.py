from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.aplicacion.comandos import CrearPagoCommand, CrearPagoHandler
from app.aplicacion.puertos import UnidadDeTrabajo
from app.aplicacion.queries import ListarPagosHandler, ObtenerPagoHandler
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_pago_repository import (
    SqlAlchemyPagoRepository,
)


def obtener_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyPagoRepository:
    return SqlAlchemyPagoRepository(session)


def obtener_unidad_de_trabajo() -> UnidadDeTrabajo:
    # Una unidad de trabajo por petición: abre y cierra su propia sesión.
    return contenedor.unidad_de_trabajo()


def obtener_handlers_de_comandos(
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> dict[type, Any]:
    # El cableado de comandos vive en el contenedor para que la API y el
    # consumidor de eventos de Pulsar ejecuten exactamente los mismos casos de uso.
    return contenedor.handlers_de_comandos(uow)



def obtener_crear_handler(handlers=Depends(obtener_handlers_de_comandos)) -> CrearPagoHandler:
    return handlers[CrearPagoCommand]


def obtener_pago_handler(repo=Depends(obtener_repo)) -> ObtenerPagoHandler:
    return ObtenerPagoHandler(repo)


def obtener_listar_handler(repo=Depends(obtener_repo)) -> ListarPagosHandler:
    return ListarPagosHandler(repo)
