from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from app.aplicacion.puertos.repositorio_eventos_salientes import RepositorioEventosSalientes
from app.dominio.billetera.billetera_repository import BilleteraRepository


class UnidadDeTrabajo(ABC):
    """Puerto que delimita la transacción de un caso de uso.

    El caso de uso decide cuándo empieza y termina la transacción; el adaptador
    decide con qué tecnología se implementa. Se usa como context manager:

        with self._uow as uow:
            billetera = uow.billeteras.obtener_por_id(...)
            billetera.acreditar(...)
            uow.billeteras.guardar(billetera)
            encolar_eventos_pendientes(billetera, uow)
            uow.confirmar()

    Al salir del bloque se revierte lo que no se haya confirmado, así que una
    excepción a mitad del caso de uso nunca deja un movimiento sin su saldo ni un
    saldo sin su movimiento. Los dos repositorios se obtienen de la unidad de
    trabajo para garantizar que todo ocurre dentro de la misma transacción: por eso
    el anuncio del hecho (`eventos_salientes`) no puede sobrevivir a un saldo que
    se revirtió, ni al revés.
    """

    billeteras: BilleteraRepository
    eventos_salientes: RepositorioEventosSalientes

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
