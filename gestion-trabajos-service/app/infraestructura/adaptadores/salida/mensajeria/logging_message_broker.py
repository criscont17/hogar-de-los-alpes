import json
import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import IntegrationEvent

logger = logging.getLogger("trabajos.integration_events")


class LoggingMessageBroker(MessageBroker):
    """Adaptador de desarrollo: escribe en logs el sobre que viajaría por Pulsar.

    Permite ejecutar el servicio sin infraestructura de mensajería. Con
    `MESSAGE_BROKER=pulsar` el contenedor inyecta `PulsarMessageBroker` sin que
    dominio ni aplicación cambien.
    """

    def publicar(self, evento: IntegrationEvent) -> None:
        envelope = {
            "event_type": evento.tipo,
            "event_version": evento.version,
            "deprecado": evento.deprecado,
            "payload": evento.como_diccionario(),
        }
        logger.info(
            "integration_event=%s %s", evento.nombre, json.dumps(envelope, ensure_ascii=False)
        )
