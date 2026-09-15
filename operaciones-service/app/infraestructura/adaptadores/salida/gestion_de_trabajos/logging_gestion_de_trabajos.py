import json
import logging

from app.aplicacion.dtos import SolicitudDeCreacionDeTrabajo
from app.aplicacion.puertos import GestionDeTrabajos

from .contrato_comandos import COMANDO_CREAR_TRABAJO, crear_trabajo_v1

logger = logging.getLogger("operaciones.comandos_trabajo")


class LoggingGestionDeTrabajos(GestionDeTrabajos):
    """Adaptador de desarrollo: registra el comando que viajaría por Pulsar.

    Sirve para probar traducciones y acuerdos sin infraestructura. El trabajo no llega a
    crearse porque GestionDeTrabajosBC nunca recibe el comando.
    """

    def solicitar_creacion(self, solicitud: SolicitudDeCreacionDeTrabajo) -> None:
        logger.info(
            "command=%s %s",
            COMANDO_CREAR_TRABAJO,
            json.dumps(crear_trabajo_v1(solicitud), ensure_ascii=False),
        )
