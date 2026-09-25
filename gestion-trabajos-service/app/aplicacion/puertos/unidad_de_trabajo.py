from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from app.dominio.trabajo.trabajo_repository import TrabajoRepository


class UnidadDeTrabajo(ABC):
    """Puerto que delimita la transacción de un caso de uso.

    El caso de uso decide cuándo empieza y termina la transacción; el adaptador decide
    con qué tecnología se implementa. Se usa como context manager:

        with self._uow as uow:
            trabajo = cargar_trabajo(uow.trabajos, comando.trabajo_id)
            trabajo.cerrar()
            uow.trabajos.guardar(trabajo)
            uow.confirmar()

    Al salir del bloque se revierte lo que no se haya confirmado, así que una excepción
    a mitad del caso de uso nunca deja escrituras a medias. Los repositorios se obtienen
    de la unidad de trabajo para garantizar que todos comparten la misma transacción.
    """

    trabajos: TrabajoRepository

    def __enter__(self) -> UnidadDeTrabajo:
        return self

    def __exit__(
        self,
        tipo: type[BaseException] | None,
        error: BaseException | None,
        rastro: TracebackType | None,
    ) -> None:
        self.revertir()

    @abstractmethod
    def confirmar(self) -> None:
        """Hace definitivos los cambios del caso de uso."""

    @abstractmethod
    def revertir(self) -> None:
        """Descarta los cambios pendientes. Después de confirmar no tiene efecto."""
