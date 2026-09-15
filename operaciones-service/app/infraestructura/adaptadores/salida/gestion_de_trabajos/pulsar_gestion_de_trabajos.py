import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from app.aplicacion.dtos import SolicitudDeCreacionDeTrabajo
from app.aplicacion.errores import GestionDeTrabajosNoDisponibleError
from app.aplicacion.puertos import GestionDeTrabajos

from .contrato_comandos import COMANDO_CREAR_TRABAJO, crear_trabajo_v1

logger = logging.getLogger("operaciones.comandos_trabajo")


class PulsarGestionDeTrabajos(GestionDeTrabajos):
    """Envía `CrearTrabajoV1` al tópico de comandos de GestionDeTrabajosBC.

    El envío espera la confirmación del broker. Si Pulsar no recibe el comando, el partner
    obtiene 503 y puede reintentar sin duplicar, porque GestionDeTrabajosBC crea un solo
    trabajo por referencia de partner.
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

    def solicitar_creacion(self, solicitud: SolicitudDeCreacionDeTrabajo) -> None:
        contenido = json.dumps(crear_trabajo_v1(solicitud), ensure_ascii=False).encode("utf-8")
        try:
            self._obtener_productor().send(
                contenido,
                properties={"command_type": COMANDO_CREAR_TRABAJO, "partner_id": solicitud.partner_id},
                partition_key=f"{solicitud.partner_id}:{solicitud.referencia_externa}",
            )
        except Exception as exc:
            self.cerrar()
            raise GestionDeTrabajosNoDisponibleError(
                "No fue posible entregar la solicitud a GestionDeTrabajosBC; reintente en unos segundos"
            ) from exc
        logger.info(
            "comando=%s partner=%s referencia=%s enviado",
            COMANDO_CREAR_TRABAJO,
            solicitud.partner_id,
            solicitud.referencia_externa,
        )

    def cerrar(self) -> None:
        with self._lock:
            for recurso in (self._productor, self._cliente):
                if recurso is not None:
                    try:
                        recurso.close()
                    except Exception:
                        logger.debug("error cerrando recurso de Pulsar", exc_info=True)
            self._productor = None
            self._cliente = None

    def _obtener_productor(self) -> Any:
        with self._lock:
            if self._productor is None:
                self._cliente = self._crear_cliente()
                self._productor = self._cliente.create_producer(
                    self._topico, send_timeout_millis=5000
                )
            return self._productor

    def _crear_cliente(self) -> Any:
        if self._fabrica_de_cliente is not None:
            return self._fabrica_de_cliente(self._url)
        import pulsar

        return pulsar.Client(self._url, operation_timeout_seconds=5, connection_timeout_ms=3000)
