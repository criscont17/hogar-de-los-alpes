from abc import ABC, abstractmethod

from app.aplicacion.dtos import RespuestaDePartner, SolicitudDeTrabajo, TrabajoDTO
from app.seedwork.aplicacion import IntegrationEvent


class AdaptadorDePartner(ABC):
    """Puerto de la capa anti-corrupción: todo lo que HdA necesita de un partner B2B2C.

    Cada partner trae su formato (JSON propio, SOAP, webhooks) y sus reglas. Los
    casos de uso solo conocen este contrato y el modelo canónico
    (`SolicitudDeTrabajo`, `TrabajoDTO`, eventos de integración). Integrar un
    partner nuevo es escribir otra implementación: dominio y aplicación no cambian.
    """

    @property
    @abstractmethod
    def partner_id(self) -> str:
        """Identificador estable del partner dentro de HdA."""

    @abstractmethod
    def traducir_solicitud(self, contenido: str) -> SolicitudDeTrabajo:
        """Convierte la petición del partner al modelo canónico y resuelve sus reglas.

        Lanza `SolicitudDePartnerInvalidaError` si no puede traducirla completa:
        nunca se crea un trabajo a partir de una traducción parcial.
        """

    @abstractmethod
    def traducir_estado(self, trabajo: TrabajoDTO) -> RespuestaDePartner:
        """Expresa el estado del trabajo en el formato que espera el partner."""

    @abstractmethod
    def notificar(self, evento: IntegrationEvent) -> None:
        """Sincroniza un hecho publicado con el core del partner.

        No debe bloquear a quien lo invoca ni propagar fallas del partner: la
        implementación decide cómo reintentar y cuándo dejar de insistir.
        """
