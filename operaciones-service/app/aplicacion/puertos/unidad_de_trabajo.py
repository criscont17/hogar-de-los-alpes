from __future__ import annotations

from abc import ABC, abstractmethod
from types import TracebackType

from app.dominio.partner.partner_repository import PartnerRepository

from .trabajos_de_partner_repository import TrabajosDePartnerRepository


class UnidadDeTrabajo(ABC):
    """Puerto que delimita la transaccion de un caso de uso.

    Aqui importa mas que en el core: crear un trabajo desde un partner lee el acuerdo del
    agregado `Partner` y escribe la vista del trabajo. Los dos repositorios salen de la
    misma unidad de trabajo, asi que comparten transaccion y se confirman juntos.

        with self._uow as uow:
            partner = cargar_partner(uow.partners, comando.partner_id)
            uow.trabajos.registrar_solicitud(vista)
            uow.confirmar()

    Al salir del bloque se revierte lo que no se haya confirmado.
    """

    partners: PartnerRepository
    trabajos: TrabajosDePartnerRepository

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
        """Descarta los cambios pendientes. Despues de confirmar no tiene efecto."""
