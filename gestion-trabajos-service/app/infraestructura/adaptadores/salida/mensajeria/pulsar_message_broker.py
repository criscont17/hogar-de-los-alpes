import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import IntegrationEvent

logger = logging.getLogger("trabajos.integration_events")


class PulsarMessageBroker(MessageBroker):
    """Publica los eventos de integración en un tópico de Apache Pulsar.

    - El cuerpo es el JSON del contrato versionado. Las propiedades del mensaje
      (`event_type`, `event_version`, `event_name`, `deprecado`, `partner_id`)
      permiten a cada consumidor filtrar sin deserializar el cuerpo.
    - La clave de partición es `trabajo_id`: con una suscripción `Key_Shared`, los
      hechos de un mismo trabajo llegan en orden aunque haya varios consumidores.
    - El envío es asíncrono para no retener la respuesta HTTP; un fallo de entrega
      se registra. Garantizar la entrega ante una caída del broker requiere el
      patrón Outbox, pendiente igual que en WalletBC.
    """

    def __init__(
        self,
        url: str,
        topico: str,
        *,
        fabrica_de_cliente: Callable[[str], Any] | None = None,
    ) -> None:
        self._url = url
        self._topico = topico
        self._fabrica_de_cliente = fabrica_de_cliente
        self._lock = threading.Lock()
        self._cliente: Any = None
        self._productor: Any = None

    def publicar(self, evento: IntegrationEvent) -> None:
        datos = evento.como_diccionario()
        propiedades = {
            "event_type": evento.tipo,
            "event_version": str(evento.version),
            "event_name": evento.nombre,
            "event_id": str(evento.event_id),
            "deprecado": str(evento.deprecado).lower(),
        }
        if datos.get("partner_id"):
            propiedades["partner_id"] = datos["partner_id"]
        self._obtener_productor().send_async(
            json.dumps(datos, ensure_ascii=False).encode("utf-8"),
            self._confirmacion(evento),
            properties=propiedades,
            partition_key=datos.get("trabajo_id") or evento.nombre,
        )

    def cerrar(self) -> None:
        with self._lock:
            if self._productor is not None:
                self._productor.flush()
                self._productor.close()
            if self._cliente is not None:
                self._cliente.close()
            self._productor = None
            self._cliente = None

    def _obtener_productor(self) -> Any:
        with self._lock:
            if self._productor is None:
                self._cliente = self._crear_cliente()
                self._productor = self._cliente.create_producer(
                    self._topico,
                    # Con el broker caído la cola se llena: mejor fallar el envío
                    # (queda en el log) que detener la respuesta al usuario.
                    block_if_queue_full=False,
                    batching_enabled=True,
                    batching_max_publish_delay_ms=10,
                )
            return self._productor

    def _crear_cliente(self) -> Any:
        if self._fabrica_de_cliente is not None:
            return self._fabrica_de_cliente(self._url)
        import pulsar

        return pulsar.Client(self._url, operation_timeout_seconds=5, connection_timeout_ms=3000)

    @staticmethod
    def _confirmacion(evento: IntegrationEvent) -> Callable[[Any, Any], None]:
        def confirmar(resultado: Any, _id_mensaje: Any) -> None:
            if getattr(resultado, "name", str(resultado)) != "Ok":
                logger.error(
                    "no se pudo publicar %s event_id=%s en Pulsar: %s",
                    evento.nombre,
                    evento.event_id,
                    resultado,
                )

        return confirmar
