import json
import logging
import threading
from typing import Any, Protocol

from app.aplicacion.errores import ConflictoDeConcurrenciaError
from app.seedwork.aplicacion import ApplicationError
from app.seedwork.dominio import DomainError

logger = logging.getLogger("trabajos.comandos")


class Ejecutor(Protocol):
    def ejecutar(self, nombre: str | None, datos: dict[str, Any]) -> None: ...


class ConsumidorDeComandosPulsar:
    """Consume el tópico de comandos de GestionDeTrabajosBC en un hilo propio.

    Política de confirmación:
    - Éxito → ack.
    - Rechazo de negocio (`DomainError`, `ApplicationError`) → ack: reintentar no
      cambia el resultado, y el hecho de rechazo ya se publicó si correspondía.
    - Conflicto de concurrencia o falla técnica (base caída, mensaje ilegible) →
      nack: Pulsar lo reentrega con espera y, tras `max_reentregas`, lo mueve a la
      dead letter queue para revisión manual.
    """

    def __init__(
        self,
        url: str,
        topico: str,
        suscripcion: str,
        ejecutor: Ejecutor,
        *,
        max_reentregas: int = 3,
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
            consumer_type=pulsar.ConsumerType.Shared,
            negative_ack_redelivery_delay_ms=self._espera_reentrega_ms,
            dead_letter_policy=pulsar.ConsumerDeadLetterPolicy(
                max_redeliver_count=self._max_reentregas
            ),
        )
        self._hilo = threading.Thread(target=self._bucle, name="pulsar-comandos", daemon=True)
        self._hilo.start()
        logger.info("consumiendo comandos de %s (suscripción %s)", self._topico, self._suscripcion)

    def detener(self) -> None:
        self._detener.set()
        if self._hilo is not None:
            self._hilo.join(timeout=5)
        if self._consumidor is not None:
            self._consumidor.close()
        if self._cliente is not None:
            self._cliente.close()

    def procesar(self, nombre: str | None, cuerpo: bytes) -> bool:
        """Ejecuta el comando y devuelve si el mensaje debe confirmarse (ack)."""

        try:
            self._ejecutor.ejecutar(nombre, json.loads(cuerpo))
        except ConflictoDeConcurrenciaError:
            logger.warning("comando=%s en conflicto de concurrencia; se reentrega", nombre)
            return False
        except (DomainError, ApplicationError) as exc:
            logger.warning("comando=%s rechazado por reglas de negocio: %s", nombre, exc)
            return True
        except Exception:
            logger.exception("comando=%s falló; se reentrega", nombre)
            return False
        logger.info("comando=%s ejecutado", nombre)
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
                logger.exception("error recibiendo comandos de Pulsar")
                continue
            if self.procesar(mensaje.properties().get("command_type"), mensaje.data()):
                self._consumidor.acknowledge(mensaje)
            else:
                self._consumidor.negative_acknowledge(mensaje)
