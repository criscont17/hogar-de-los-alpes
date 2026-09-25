import json
import logging
import threading
from decimal import Decimal
from typing import Any

logger = logging.getLogger("pagos.comandos_saga")


class ConsumidorComandosPagosPulsar:
    """Consume comandos de la Saga dirigidos a PagosBC (autorizar o revertir pago)."""

    def __init__(
        self,
        url: str,
        topico_comandos: str,
        topico_eventos: str,
        suscripcion: str,
        procesador,
    ) -> None:
        self._url = url
        self._topico_comandos = topico_comandos
        self._topico_eventos = topico_eventos
        self._suscripcion = suscripcion
        self._procesador = procesador
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._cliente: Any = None
        self._consumidor: Any = None
        self._productor: Any = None

    def iniciar(self) -> None:
        import pulsar

        self._cliente = pulsar.Client(
            self._url, operation_timeout_seconds=10, connection_timeout_ms=5000
        )
        self._consumidor = self._cliente.subscribe(
            self._topico_comandos,
            self._suscripcion,
            consumer_type=pulsar.ConsumerType.Shared,
        )
        self._productor = self._cliente.create_producer(
            self._topico_eventos,
            block_if_queue_full=True,
            max_pending_messages=1000,
        )
        self._hilo = threading.Thread(
            target=self._bucle_consumo, daemon=True, name="pagos-comandos-saga"
        )
        self._hilo.start()
        logger.info("Consumidor de comandos de saga en PagosBC iniciado en %s", self._topico_comandos)

    def _bucle_consumo(self) -> None:
        while not self._detener.is_set():
            try:
                msg = self._consumidor.receive(timeout_millis=1000)
            except Exception:
                continue

            try:
                props = msg.properties() or {}
                tipo_comando = props.get("command_type")
                saga_id = props.get("saga_id")
                datos = json.loads(msg.data().decode("utf-8"))

                if not tipo_comando and "command_type" in datos:
                    tipo_comando = datos["command_type"]
                if not saga_id and "saga_id" in datos:
                    saga_id = datos["saga_id"]

                payload = datos.get("payload", datos)
                self._procesar_comando(tipo_comando, saga_id, payload)
                self._consumidor.acknowledge(msg)
            except Exception:
                logger.exception("Error procesando comando de saga en PagosBC")
                try:
                    self._consumidor.acknowledge(msg)
                except Exception:
                    pass

    def _procesar_comando(self, tipo_comando: str | None, saga_id: str | None, payload: dict[str, Any]) -> None:
        if not tipo_comando or not saga_id:
            return

        trabajo_id = payload.get("trabajo_id", "")
        simular_fallo = payload.get("simular_fallo", False)

        if tipo_comando == "AutorizarPagoTrabajoV1":
            resultado = self._procesador.autorizar(
                saga_id=saga_id,
                trabajo_id=trabajo_id,
                monto=Decimal(str(payload["monto"])),
                moneda=str(payload["moneda"]),
                simular_fallo=simular_fallo,
            )
            if not resultado.exitoso:
                self._emitir_evento(
                    tipo_evento="PagoTrabajoRechazadoV1",
                    saga_id=saga_id,
                    payload={
                        "trabajo_id": trabajo_id,
                        "motivo": resultado.motivo or "El pago fue rechazado",
                    },
                    partition_key=trabajo_id,
                )
            else:
                self._emitir_evento(
                    tipo_evento="PagoTrabajoAutorizadoV1",
                    saga_id=saga_id,
                    payload={
                        "trabajo_id": trabajo_id,
                        "monto": str(payload["monto"]),
                        "moneda": str(payload["moneda"]),
                        "estado": "AUTORIZADO",
                    },
                    partition_key=trabajo_id,
                )

        elif tipo_comando == "RevertirPagoTrabajoV1":
            resultado = self._procesador.revertir(
                saga_id=saga_id,
                trabajo_id=trabajo_id,
                motivo=str(payload.get("motivo", "Compensación de Saga")),
            )
            self._emitir_evento(
                tipo_evento="PagoTrabajoRevertidoV1",
                saga_id=saga_id,
                payload={
                    "trabajo_id": trabajo_id,
                    "revertido": resultado.exitoso,
                    "motivo": resultado.motivo,
                },
                partition_key=trabajo_id,
            )

    def _emitir_evento(
        self,
        tipo_evento: str,
        saga_id: str,
        payload: dict[str, Any],
        partition_key: str,
    ) -> None:
        cuerpo = {
            "event_type": tipo_evento,
            "event_name": tipo_evento,
            "saga_id": saga_id,
            "payload": payload,
        }
        bytes_msg = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
        self._productor.send(
            bytes_msg,
            properties={"event_type": tipo_evento, "saga_id": saga_id},
            partition_key=partition_key,
        )
        logger.info("Evento %s emitido hacia %s para saga=%s", tipo_evento, self._topico_eventos, saga_id)

    def detener(self) -> None:
        self._detener.set()
        if self._consumidor:
            try:
                self._consumidor.close()
            except Exception:
                pass
        if self._productor:
            try:
                self._productor.close()
            except Exception:
                pass
        if self._cliente:
            try:
                self._cliente.close()
            except Exception:
                pass
