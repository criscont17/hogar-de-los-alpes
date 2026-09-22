from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.aplicacion.puertos import UnidadDeTrabajo
from app.dominio.errores import BilleteraDuplicadaError

from .db import SessionLocal
from .sqlalchemy_billetera_repository import SqlAlchemyBilleteraRepository


class SqlAlchemyUnidadDeTrabajo(UnidadDeTrabajo):
    """Unidad de trabajo sobre una sesión de SQLAlchemy.

    Abre una sesión al entrar al bloque y la cierra al salir, así que la misma
    clase sirve para una petición HTTP y para un comando de saga que llega por
    Pulsar. Los errores de la base se traducen aquí porque, al sacar el `commit`
    del repositorio, es al confirmar cuando aparecen.
    """

    def __init__(self, fabrica_de_sesiones: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnidadDeTrabajo:
        self._session = self._fabrica_de_sesiones()
        self.billeteras = SqlAlchemyBilleteraRepository(self._session)
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
        except IntegrityError as exc:
            sesion.rollback()
            raise BilleteraDuplicadaError("El proveedor ya tiene una billetera") from exc
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
