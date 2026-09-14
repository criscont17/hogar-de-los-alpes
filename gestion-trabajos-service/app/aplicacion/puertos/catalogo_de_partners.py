from abc import ABC, abstractmethod

from .adaptador_de_partner import AdaptadorDePartner


class CatalogoDePartners(ABC):
    """Puerto para encontrar el adaptador de un partner por su identificador."""

    @abstractmethod
    def obtener(self, partner_id: str) -> AdaptadorDePartner:
        """Devuelve el adaptador o lanza `PartnerNoRegistradoError`."""

    @abstractmethod
    def partner_ids(self) -> tuple[str, ...]:
        """Partners integrados actualmente."""
