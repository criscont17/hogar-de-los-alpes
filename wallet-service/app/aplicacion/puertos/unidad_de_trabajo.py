from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from app.dominio.billetera.billetera_repository import BilleteraRepository


class UnidadDeTrabajo(ABC):
    """Puerto que delimita la transacción de un caso de uso.

    El caso de uso decide cuándo empieza y termina la transacción; el adaptador
    decide con qué tecnología se implementa. Se usa como context manager:

        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_id(...)
            billetera.acreditar(...)
            uow.billeteras.guardar(billetera)
            uow.confirmar()

    Al salir del bloque se revierte lo que no se haya confirmado, así que una
    excepción a mitad del caso de uso nunca deja un movimiento sin su saldo ni un
    saldo sin su movimiento. El repositorio se obtiene de la unidad de trabajo para
    garantizar que todo ocurre dentro de la misma transacción.
    """

    billeteras: BilleteraRepository

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
