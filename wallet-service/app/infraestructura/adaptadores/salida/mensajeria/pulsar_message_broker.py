import json
import threading
from collections.abc import Callable
from typing import Any

from app.aplicacion.puertos import MessageBroker
from app.seedwork.aplicacion import SobreDeEvento


class PulsarMessageBroker(MessageBroker):
    """Publica los eventos de integración de WalletBC en un tópico de Pulsar.

    A diferencia del adaptador equivalente en GestionDeTrabajos, **envía de forma
    síncrona**: su único cliente es el relay de la bandeja de salida, que solo
    puede marcar una fila como publicada si tiene la confirmación del broker. Un
    `send_async` retornaría antes de saberlo y haría perder eventos justo en el
    caso que el patrón existe para cubrir; el costo de esperar el *ack* lo paga un
    hilo de fondo, no la respuesta al usuario.

    Por la misma razón deja que las excepciones suban: el fallo de entrega es la
    señal que el relay necesita para reintentar con espera creciente.
    """

    def __init__(
        self,
        url: str,
        topico: str,
        *,
        tiempo_de_envio_ms: int = 5000,
        fabrica_de_cliente: Callable[[str], Any] | None = None,
    ) -> None:
        self._url = url
        self._topico = topico
        self._tiempo_de_envio_ms = tiempo_de_envio_ms
        self._fabrica_de_cliente = fabrica_de_cliente
        self._lock = threading.Lock()
        self._cliente: Any = None
        self._productor: Any = None

    def publicar(self, sobre: SobreDeEvento) -> None:
        try:
            self._obtener_productor().send(
                json.dumps(sobre.payload, ensure_ascii=False).encode("utf-8"),
                properties={
                    "event_type": sobre.tipo,
                    "event_id": str(sobre.event_id),
                    "origen": "wallet-service",
                },
                # Agrupa por billetera: los movimientos de un mismo saldo llegan en orden.
                partition_key=sobre.clave_particion or sobre.tipo,
            )
        except Exception:
            # Una conexión que se cayó no se recupera sola: se descarta para que el
            # siguiente ciclo del relay la reconstruya contra el broker que volvió.
            self.cerrar()
            raise

    def cerrar(self) -> None:
        with self._lock:
            self._descartar(self._productor)
            self._descartar(self._cliente)
            self._productor = None
            self._cliente = None

    def _obtener_productor(self) -> Any:
        with self._lock:
            if self._productor is None:
                cliente = self._crear_cliente()
                try:
                    self._productor = cliente.create_producer(
                        self._topico,
                        send_timeout_millis=self._tiempo_de_envio_ms,
                        block_if_queue_full=True,
                        max_pending_messages=1000,
                    )
                except Exception:
                    # Sin productor el cliente no sirve y nadie más lo referencia.
                    self._descartar(cliente)
                    raise
                self._cliente = cliente
            return self._productor

    @staticmethod
    def _descartar(recurso: Any) -> None:
        if recurso is None:
            return
        try:
            recurso.close()
        except Exception:
            pass

    def _crear_cliente(self) -> Any:
        if self._fabrica_de_cliente is not None:
            return self._fabrica_de_cliente(self._url)
        import pulsar

        return pulsar.Client(self._url, operation_timeout_seconds=5, connection_timeout_ms=3000)
