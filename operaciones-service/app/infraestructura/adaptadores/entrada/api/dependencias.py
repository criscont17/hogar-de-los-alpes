from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session

from app.aplicacion.comandos import (
    CrearTrabajoDesdePartnerCommand,
    CrearTrabajoDesdePartnerHandler,
    RegistrarPartnerCommand,
    RegistrarPartnerHandler,
)
from app.aplicacion.puertos import UnidadDeTrabajo
from app.aplicacion.queries import (
    ConsultarTrabajoDePartnerHandler,
    ListarPartnersHandler,
    ObtenerPartnerHandler,
)
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.acl_partners import CatalogoDeAdaptadoresEnMemoria
from app.infraestructura.adaptadores.salida.persistencia.db import obtener_sesion
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_partner_repository import (
    SqlAlchemyPartnerRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajos_de_partner_repository import (
    SqlAlchemyTrabajosDePartnerRepository,
)


def obtener_catalogo() -> CatalogoDeAdaptadoresEnMemoria:
    return contenedor.obtener_catalogo_adaptadores()


def obtener_partners_repo(session: Session = Depends(obtener_sesion)) -> SqlAlchemyPartnerRepository:
    return SqlAlchemyPartnerRepository(session)


def obtener_trabajos_repo(
    session: Session = Depends(obtener_sesion),
) -> SqlAlchemyTrabajosDePartnerRepository:
    return SqlAlchemyTrabajosDePartnerRepository(session)


def obtener_unidad_de_trabajo() -> UnidadDeTrabajo:
    # Una unidad de trabajo por peticion: abre y cierra su propia sesion.
    return contenedor.unidad_de_trabajo()


def obtener_handlers_de_comandos(
    uow: UnidadDeTrabajo = Depends(obtener_unidad_de_trabajo),
) -> dict[type, Any]:
    # El cableado vive en el contenedor para que la API y el consumidor de Pulsar
    # ejecuten exactamente los mismos casos de uso.
    return contenedor.handlers_de_comandos(uow)


def obtener_registrar_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> RegistrarPartnerHandler:
    return handlers[RegistrarPartnerCommand]


def obtener_crear_desde_partner_handler(
    handlers=Depends(obtener_handlers_de_comandos),
) -> CrearTrabajoDesdePartnerHandler:
    return handlers[CrearTrabajoDesdePartnerCommand]


def obtener_listar_handler(
    repo=Depends(obtener_partners_repo), catalogo=Depends(obtener_catalogo)
) -> ListarPartnersHandler:
    return ListarPartnersHandler(repo, catalogo)


def obtener_partner_handler(
    repo=Depends(obtener_partners_repo), catalogo=Depends(obtener_catalogo)
) -> ObtenerPartnerHandler:
    return ObtenerPartnerHandler(repo, catalogo)


def obtener_consultar_handler(
    catalogo=Depends(obtener_catalogo), trabajos=Depends(obtener_trabajos_repo)
) -> ConsultarTrabajoDePartnerHandler:
    return ConsultarTrabajoDePartnerHandler(catalogo, trabajos)
