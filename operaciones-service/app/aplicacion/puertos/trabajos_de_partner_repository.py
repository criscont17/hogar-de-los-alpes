from abc import ABC, abstractmethod

from app.aplicacion.dtos import TrabajoDePartnerDTO


class TrabajosDePartnerRepository(ABC):
    """Puerto de la vista de trabajos por partner, el modelo de lectura de OperacionesBC."""

    @abstractmethod
    def obtener(self, partner_id: str, referencia_externa: str) -> TrabajoDePartnerDTO | None:
        """Vista del trabajo que el partner identifica con su referencia."""

    @abstractmethod
    def registrar_solicitud(self, trabajo: TrabajoDePartnerDTO) -> TrabajoDePartnerDTO:
        """Guarda una solicitud nueva y devuelve la vista vigente.

        Si ya existía una vista no rechazada, la conserva: pudo avanzar con eventos que
        llegaron antes de guardar la solicitud.
        """

    @abstractmethod
    def guardar(self, trabajo: TrabajoDePartnerDTO) -> None:
        """Reemplaza la vista del trabajo."""
