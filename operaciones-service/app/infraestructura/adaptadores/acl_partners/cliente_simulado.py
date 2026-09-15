import logging

from .mensaje import MensajeParaPartner

logger = logging.getLogger("operaciones.partners")


class ClientePartnerSimulado:
    """Hace las veces del core del partner.

    En producción sería un cliente HTTP, SOAP o de webhooks con timeout. Aquí registra lo
    recibido y permite simular una caída para observar el circuit breaker.
    """

    def __init__(self, partner_id: str) -> None:
        self.partner_id = partner_id
        self.disponible = True
        self._recibidos: list[MensajeParaPartner] = []

    @property
    def recibidos(self) -> tuple[MensajeParaPartner, ...]:
        return tuple(self._recibidos)

    def enviar(self, mensaje: MensajeParaPartner) -> None:
        if not self.disponible:
            raise ConnectionError(f"El core del partner {self.partner_id} no responde")
        self._recibidos.append(mensaje)
        logger.info(
            "partner_core=%s recibio operacion=%s media_type=%s contenido=%s",
            self.partner_id,
            mensaje.operacion,
            mensaje.media_type,
            mensaje.contenido,
        )
