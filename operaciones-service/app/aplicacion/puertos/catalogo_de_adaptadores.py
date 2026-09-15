from abc import ABC, abstractmethod

from .adaptador_de_partner import AdaptadorDePartner


class CatalogoDeAdaptadores(ABC):
    """Puerto para encontrar el adaptador de integración de un partner."""

    @abstractmethod
    def obtener(self, partner_id: str) -> AdaptadorDePartner:
        """Devuelve el adaptador o lanza `AdaptadorNoDisponibleError`."""

    @abstractmethod
    def tiene(self, partner_id: str) -> bool:
        """Indica si ya existe un adaptador para el partner."""
