import json
import logging

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import SobreDeEvento

logger = logging.getLogger("wallet.integration_events")


class LoggingMessageBroker(MessageBroker):
    """Adaptador simulado: escribe el sobre que viajaría en lugar de enviarlo.

    Sirve para correr el servicio sin Pulsar. Como nunca falla, el relay de la
    bandeja de salida marca todo `PUBLICADO` de inmediato: es útil para ver el
    flujo, no para demostrar la garantía de entrega.
    """

    def publicar(self, sobre: SobreDeEvento) -> None:
        envelope = {
            "event_type": sobre.tipo,
            "event_id": str(sobre.event_id),
            "partition_key": sobre.clave_particion,
            "payload": sobre.payload,
        }
        logger.info("integration_event=%s", json.dumps(envelope, ensure_ascii=False))
