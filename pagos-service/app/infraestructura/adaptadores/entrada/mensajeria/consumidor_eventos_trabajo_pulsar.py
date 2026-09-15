import json
import logging
import threading
from collections.abc import Mapping
from typing import Any, Protocol

from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.aplicacion.errores import LiquidacionInvalidaError
from app.seedwork.aplicacion import ApplicationError
from app.seedwork.dominio import DomainError

logger = logging.getLogger("pagos.eventos_trabajo")

_EVENTO_DE_INTERES = "TrabajoCerradoV1"


class Ejecutor(Protocol):
    def ejecutar(self, evento: EventoDeTrabajoRecibido) -> None: ...


class ConsumidorDeEventosDeTrabajoPulsar:
    """Consume el Published Language de GestionDeTrabajosBC en un hilo propio.

    - Suscripción `Key_Shared`: los hechos de un mismo trabajo (misma clave
      `trabajo_id`) llegan en orden aunque haya varias réplicas de PagosBC.
    - Solo procesa `TrabajoCerradoV1` (el hecho pivote que libera el pago);
      cualquier otro evento del contexto de Trabajo se confirma sin leerlo.
    - Rechazos de negocio → ack. Fallas técnicas → nack; tras varias
      reentregas, Pulsar mueve el mensaje a la dead letter queue.
    """

    def __init__(
        self,
        url: str,
        topico: str,
        suscripcion: str,
        ejecutor: Ejecutor,
        *,
        max_reentregas: int = 5,
        espera_reentrega_ms: int = 2000,
    ) -> None:
        self._url = url
        self._topico = topico
        self._suscripcion = suscripcion
        self._ejecutor = ejecutor
        self._max_reentregas = max_reentregas
        self._espera_reentrega_ms = espera_reentrega_ms
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._cliente: Any = None
        self._consumidor: Any = None

    def iniciar(self) -> None:
        import pulsar

        self._cliente = pulsar.Client(
            self._url, operation_timeout_seconds=10, connection_timeout_ms=5000
        )
        self._consumidor = self._cliente.subscribe(
            self._topico,
            self._suscripcion,
            consumer_type=pulsar.ConsumerType.KeyShared,
            initial_position=pulsar.InitialPosition.Earliest,
            negative_ack_redelivery_delay_ms=self._espera_reentrega_ms,
            dead_letter_policy=pulsar.ConsumerDeadLetterPolicy(
                max_redeliver_count=self._max_reentregas
            ),
        )
        self._hilo = threading.Thread(target=self._bucle, name="pulsar-eventos-trabajo", daemon=True)
        self._hilo.start()
        logger.info("consumiendo eventos de %s (suscripción %s)", self._topico, self._suscripcion)

    def detener(self) -> None:
        self._detener.set()
        if self._hilo is not None:
            self._hilo.join(timeout=5)
        if self._consumidor is not None:
            self._consumidor.close()
        if self._cliente is not None:
            self._cliente.close()

    def procesar(self, propiedades: Mapping[str, str], cuerpo: bytes) -> bool:
        """Procesa el evento y devuelve si el mensaje debe confirmarse (ack)."""

        nombre = propiedades.get("event_name", "")
        if nombre != _EVENTO_DE_INTERES:
            return True
        try:
            self._ejecutor.ejecutar(EventoDeTrabajoRecibido(nombre, json.loads(cuerpo)))
        except (DomainError, ApplicationError, LiquidacionInvalidaError) as exc:
            logger.warning("evento=%s descartado por reglas de negocio: %s", nombre, exc)
            return True
        except Exception:
            logger.exception("evento=%s falló; se reentrega", nombre)
            return False
        return True

    def _bucle(self) -> None:
        import pulsar

        while not self._detener.is_set():
            try:
                mensaje = self._consumidor.receive(timeout_millis=1000)
            except pulsar.Timeout:
                continue
            except Exception:
                if self._detener.is_set():
                    break
                logger.exception("error recibiendo eventos de Pulsar")
                continue
            if self.procesar(mensaje.properties(), mensaje.data()):
                self._consumidor.acknowledge(mensaje)
            else:
                self._consumidor.negative_acknowledge(mensaje)
