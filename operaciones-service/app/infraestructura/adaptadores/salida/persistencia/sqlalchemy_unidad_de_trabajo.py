from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from app.aplicacion.puertos import UnidadDeTrabajo

from .db import SessionLocal
from .sqlalchemy_partner_repository import SqlAlchemyPartnerRepository
from .sqlalchemy_trabajos_de_partner_repository import SqlAlchemyTrabajosDePartnerRepository


class SqlAlchemyUnidadDeTrabajo(UnidadDeTrabajo):
    """Unidad de trabajo sobre una sesion de SQLAlchemy.

    Abre una sesion al entrar al bloque y la cierra al salir, asi que la misma instancia
    sirve para una peticion HTTP o para un evento de Pulsar. Los dos repositorios se
    construyen sobre esa sesion: lo que escriban se confirma o se revierte junto.
    """

    def __init__(self, fabrica_de_sesiones: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnidadDeTrabajo:
        self._session = self._fabrica_de_sesiones()
        self.partners = SqlAlchemyPartnerRepository(self._session)
        self.trabajos = SqlAlchemyTrabajosDePartnerRepository(self._session)
        return self

    def __exit__(self, tipo, error, rastro) -> None:
        try:
            self.revertir()
        finally:
            if self._session is not None:
                self._session.close()
            self._session = None

    def confirmar(self) -> None:
        sesion = self._sesion()
        try:
            sesion.commit()
        except Exception:
            sesion.rollback()
            raise

    def revertir(self) -> None:
        if self._session is not None:
            self._session.rollback()

    def _sesion(self) -> Session:
        if self._session is None:
            raise RuntimeError("La unidad de trabajo debe usarse dentro de un bloque `with`")
        return self._session
