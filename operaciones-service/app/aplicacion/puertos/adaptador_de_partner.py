from abc import ABC, abstractmethod

from app.aplicacion.dtos import (
    EventoDeTrabajoRecibido,
    RespuestaDePartner,
    SolicitudDePartner,
    TrabajoDePartnerDTO,
)


class AdaptadorDePartner(ABC):
    """Puerto de la capa anti-corrupción: todo lo que HdA necesita del formato de un partner.

    Cada partner B2B2C trae su propio formato (JSON, SOAP, webhooks, texto). Un adaptador
    solo traduce: las reglas comerciales viven en el `AcuerdoComercial` del agregado
    `Partner`. Integrar un partner nuevo es escribir otra implementación.
    """

    @property
    @abstractmethod
    def partner_id(self) -> str:
        """Identificador del partner al que traduce."""

    @abstractmethod
    def traducir_solicitud(self, contenido: str) -> SolicitudDePartner:
        """Convierte la petición del partner al modelo canónico.

        Lanza `SolicitudDePartnerInvalidaError` si no puede traducirla completa: nunca se
        solicita un trabajo a partir de una traducción parcial.
        """

    @abstractmethod
    def traducir_estado(self, trabajo: TrabajoDePartnerDTO) -> RespuestaDePartner:
        """Expresa el estado del trabajo en el formato que espera el partner."""

    @abstractmethod
    def notificar(self, evento: EventoDeTrabajoRecibido) -> None:
        """Sincroniza un hecho con el core del partner.

        No debe bloquear a quien lo invoca ni propagar fallas del partner.
        """
