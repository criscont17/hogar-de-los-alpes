import json
import logging
import threading
from typing import Any
from uuid import UUID

logger = logging.getLogger("trabajos.consumidor_eventos_saga")


class ConsumidorEventosSagaPulsar:
    """Consume los eventos emitidos por PagosBC y OperacionesBC para la Saga.

    Escucha tópicos con suscripción Shared para hacer avanzar la máquina de estados.
    """

    def __init__(
        self,
        url: str,
        topicos: list[str],
        suscripcion: str,
        orquestador,
    ) -> None:
        self._url = url
        self._topicos = topicos
        self._suscripcion = suscripcion
        self._orquestador = orquestador
        self._detener = threading.Event()
        self._hilos: list[threading.Thread] = []
        self._consumidores: list[Any] = []
        self._cliente: Any = None

    def iniciar(self) -> None:
        import pulsar

        self._cliente = pulsar.Client(
            self._url, operation_timeout_seconds=10, connection_timeout_ms=5000
        )
        for topico in self._topicos:
            try:
                consumidor = self._cliente.subscribe(
                    topico,
                    self._suscripcion,
                    consumer_type=pulsar.ConsumerType.Shared,
                )
                self._consumidores.append(consumidor)
                hilo = threading.Thread(
                    target=self._bucle_consumo,
                    args=(consumidor, topico),
                    daemon=True,
                    name=f"saga-evento-{topico}",
                )
                self._hilos.append(hilo)
                hilo.start()
                logger.info("Consumidor de eventos de saga iniciado en %s", topico)
            except Exception:
                logger.exception("No se pudo suscribir al tópico de saga %s", topico)

    def _bucle_consumo(self, consumidor: Any, topico: str) -> None:
        while not self._detener.is_set():
            try:
                msg = consumidor.receive(timeout_millis=1000)
            except Exception:
                continue

            try:
                props = msg.properties() or {}
                tipo_evento = props.get("event_type") or props.get("event_name")
                saga_id_str = props.get("saga_id")
                datos = json.loads(msg.data().decode("utf-8"))

                if not saga_id_str and "saga_id" in datos:
                    saga_id_str = datos["saga_id"]
                if not tipo_evento and "event_type" in datos:
                    tipo_evento = datos["event_type"]

                if saga_id_str and tipo_evento:
                    saga_id = UUID(saga_id_str)
                    payload = datos.get("payload", datos)
                    self._despachar_a_orquestador(tipo_evento, saga_id, payload)

                consumidor.acknowledge(msg)
            except Exception:
                logger.exception("Error procesando evento de saga en %s", topico)
                try:
                    consumidor.acknowledge(msg)
                except Exception:
                    pass

    def _despachar_a_orquestador(self, tipo_evento: str, saga_id: UUID, payload: dict[str, Any]) -> None:
        if tipo_evento == "PagoTrabajoAutorizadoV1":
            self._orquestador.procesar_pago_autorizado(saga_id, payload)
        elif tipo_evento == "PagoTrabajoRechazadoV1":
            self._orquestador.procesar_pago_rechazado(saga_id, payload)
        elif tipo_evento == "ProveedorTrabajoAsignadoV1":
            self._orquestador.procesar_proveedor_asignado(saga_id, payload)
        elif tipo_evento == "AsignacionProveedorRechazadaV1":
            self._orquestador.procesar_proveedor_rechazado(saga_id, payload)

    def detener(self) -> None:
        self._detener.set()
        for c in self._consumidores:
            try:
                c.close()
            except Exception:
                pass
        if self._cliente:
            try:
                self._cliente.close()
            except Exception:
                pass
