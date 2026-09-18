import json
import logging
import threading
from typing import Any
from uuid import UUID

logger = logging.getLogger("trabajos.saga_commands")


class PulsarSagaCommandPublisher:
    """Publica comandos de la Saga hacia los tópicos de Pagos y Operaciones."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._lock = threading.Lock()
        self._cliente: Any = None
        self._productores: dict[str, Any] = {}

    def _obtener_productor(self, topico: str) -> Any:
        import pulsar

        with self._lock:
            if self._cliente is None:
                self._cliente = pulsar.Client(
                    self._url, operation_timeout_seconds=10, connection_timeout_ms=5000
                )
            if topico not in self._productores:
                self._productores[topico] = self._cliente.create_producer(
                    topico, block_if_queue_full=True, max_pending_messages=1000
                )
            return self._productores[topico]

    def enviar_comando(
        self,
        topico: str,
        tipo_comando: str,
        saga_id: UUID,
        payload: dict[str, Any],
        partition_key: str | None = None,
    ) -> None:
        cuerpo = {
            "command_type": tipo_comando,
            "saga_id": str(saga_id),
            "payload": payload,
        }
        bytes_mensaje = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        productor = self._obtener_productor(topico)
        productor.send(
            bytes_mensaje,
            properties={"command_type": tipo_comando, "saga_id": str(saga_id)},
            partition_key=partition_key or str(saga_id),
        )
        logger.info("Comando %s enviado a %s para saga=%s", tipo_comando, topico, saga_id)

    def cerrar(self) -> None:
        with self._lock:
            for prod in self._productores.values():
                try:
                    prod.close()
                except Exception:
                    pass
            self._productores.clear()
            if self._cliente:
                try:
                    self._cliente.close()
                except Exception:
                    pass
                self._cliente = None
