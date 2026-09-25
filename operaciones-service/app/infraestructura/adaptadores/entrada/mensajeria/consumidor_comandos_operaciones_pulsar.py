import json
import logging
import threading
from typing import Any

logger = logging.getLogger("operaciones.comandos_saga")


class ConsumidorComandosOperacionesPulsar:
    """Consume comandos de la Saga dirigidos a OperacionesBC (asignar o liberar proveedor)."""

    def __init__(
        self,
        url: str,
        topico_comandos: str,
        topico_eventos: str,
        suscripcion: str,
    ) -> None:
        self._url = url
        self._topico_comandos = topico_comandos
        self._topico_eventos = topico_eventos
        self._suscripcion = suscripcion
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
            target=self._bucle_consumo, daemon=True, name="operaciones-comandos-saga"
        )
        self._hilo.start()
        logger.info(
            "Consumidor de comandos de saga en OperacionesBC iniciado en %s",
            self._topico_comandos,
        )

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
                logger.exception("Error procesando comando de saga en OperacionesBC")
                try:
                    self._consumidor.acknowledge(msg)
                except Exception:
                    pass

    def _procesar_comando(
        self, tipo_comando: str | None, saga_id: str | None, payload: dict[str, Any]
    ) -> None:
        if not tipo_comando or not saga_id:
            return

        trabajo_id = payload.get("trabajo_id", "")
        simular_fallo = payload.get("simular_fallo", False)

        if tipo_comando == "AsignarProveedorTrabajoV1":
            if simular_fallo:
                logger.warning(
                    "Simulando rechazo de asignación de proveedor para saga=%s trabajo=%s",
                    saga_id,
                    trabajo_id,
                )
                self._emitir_evento(
                    tipo_evento="AsignacionProveedorRechazadaV1",
                    saga_id=saga_id,
                    payload={
                        "trabajo_id": trabajo_id,
                        "motivo": "Sin proveedores con cobertura en la zona (simulación de fallo)",
                    },
                    partition_key=trabajo_id,
                )
            else:
                proveedor_id = "prov-hda-expert-01"
                logger.info(
                    "Proveedor %s asignado para saga=%s trabajo=%s",
                    proveedor_id,
                    saga_id,
                    trabajo_id,
                )
                self._emitir_evento(
                    tipo_evento="ProveedorTrabajoAsignadoV1",
                    saga_id=saga_id,
                    payload={
                        "trabajo_id": trabajo_id,
                        "proveedor_id": proveedor_id,
                        "partner_id": payload.get("partner_id"),
                        "estado": "ASIGNADO",
                    },
                    partition_key=trabajo_id,
                )
                self._reportar_ejecucion(
                    saga_id=saga_id,
                    trabajo_id=trabajo_id,
                    proveedor_id=proveedor_id,
                    fallo=bool(payload.get("simular_fallo_ejecucion", False)),
                )

        elif tipo_comando == "LiberarAsignacionProveedorV1":
            logger.info("Compensación: Liberar asignación para saga=%s trabajo=%s", saga_id, trabajo_id)
            self._emitir_evento(
                tipo_evento="AsignacionProveedorLiberadaV1",
                saga_id=saga_id,
                payload={
                    "trabajo_id": trabajo_id,
                    "liberado": True,
                    "motivo": payload.get("motivo", "Compensación de Saga"),
                },
                partition_key=trabajo_id,
            )

    def _reportar_ejecucion(
        self, saga_id: str, trabajo_id: str, proveedor_id: str, fallo: bool
    ) -> None:
        """Reporta al orquestador cómo terminó el trabajo en campo.

        En la POC el trabajo físico se simula: el proveedor asignado lo ejecuta de
        inmediato. En producción este evento lo dispararía la confirmación del
        proveedor (evidencias, cierre del sub-trabajo), no la asignación.
        """

        if fallo:
            logger.warning(
                "Simulando ejecución fallida para saga=%s trabajo=%s", saga_id, trabajo_id
            )
            self._emitir_evento(
                tipo_evento="EjecucionTrabajoFallidaV1",
                saga_id=saga_id,
                payload={
                    "trabajo_id": trabajo_id,
                    "proveedor_id": proveedor_id,
                    "motivo": "El proveedor no pudo ejecutar el trabajo en sitio (simulación de fallo)",
                },
                partition_key=trabajo_id,
            )
            return

        self._emitir_evento(
            tipo_evento="EjecucionTrabajoCompletadaV1",
            saga_id=saga_id,
            payload={
                "trabajo_id": trabajo_id,
                "proveedor_id": proveedor_id,
                "estado": "EJECUTADO",
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
        logger.info(
            "Evento %s emitido hacia %s para saga=%s",
            tipo_evento,
            self._topico_eventos,
            saga_id,
        )

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
