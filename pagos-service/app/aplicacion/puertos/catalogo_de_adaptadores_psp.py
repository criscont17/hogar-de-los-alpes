from abc import ABC, abstractmethod

from .adaptador_de_psp import AdaptadorDePSP


class CatalogoDePSP(ABC):
    """Puerto para resolver el adaptador de PSP adecuado para un pago."""

    @abstractmethod
    def obtener(self, psp_id: str) -> AdaptadorDePSP:
        """Devuelve el adaptador o lanza `PSPNoSoportadoError`."""

    @abstractmethod
    def tiene(self, psp_id: str) -> bool: ...

    @abstractmethod
    def psp_por_defecto(self, moneda: str) -> str:
        """PSP que procesa una moneda cuando el llamador no pide uno explícito.

        Lanza `PSPNoSoportadoError` si ningún adaptador registrado la procesa;
        así se hace explícito que un país nuevo requiere onboarding de su PSP.
        """
