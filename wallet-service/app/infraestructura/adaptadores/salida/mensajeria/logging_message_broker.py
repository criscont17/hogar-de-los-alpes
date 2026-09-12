import json
import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import IntegrationEvent

logger = logging.getLogger("wallet.integration_events")


class LoggingMessageBroker(MessageBroker):
    """Adaptador simulado: escribe el evento en logs con el sobre que viajaría.

    Sustituirlo por RabbitMQ o SQS es implementar `MessageBroker` en esta misma
    carpeta y cambiar la instancia que se inyecta en `dependencias.py`.
    """

    def publicar(self, evento: IntegrationEvent) -> None:
        envelope = {
            "event_type": evento.nombre,
            "payload": evento.como_diccionario(),
        }
        logger.info("integration_event=%s", json.dumps(envelope))
