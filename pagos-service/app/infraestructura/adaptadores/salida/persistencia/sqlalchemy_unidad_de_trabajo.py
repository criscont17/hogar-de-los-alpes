from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.aplicacion.errores import ConflictoDeConcurrenciaError
from app.aplicacion.puertos import UnidadDeTrabajo
from app.dominio.errores import PagoDuplicadoError

from .db import SessionLocal
from .sqlalchemy_pago_repository import SqlAlchemyPagoRepository


class SqlAlchemyUnidadDeTrabajo(UnidadDeTrabajo):
    """Unidad de trabajo sobre una sesión de SQLAlchemy.

    Abre una sesión al entrar al bloque y la cierra al salir, así que la misma instancia
    sirve para una petición HTTP o para un mensaje de Pulsar. Los errores de la base se
    traducen aquí porque, al sacar el `commit` del repositorio, es al confirmar cuando
    aparecen.
    """

    def __init__(self, fabrica_de_sesiones: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones
        self._session: Session | None = None

    def __enter__(self) -> SqlAlchemyUnidadDeTrabajo:
        self._session = self._fabrica_de_sesiones()
        self.pagos = SqlAlchemyPagoRepository(self._session)
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
            raise PagoDuplicadoError(
                "Ya existe un pago con esa referencia externa"
            ) from exc
        except StaleDataError as exc:
            sesion.rollback()
            raise ConflictoDeConcurrenciaError(
                "El pago fue modificado por otra operación; vuelva a intentarlo"
            ) from exc
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
