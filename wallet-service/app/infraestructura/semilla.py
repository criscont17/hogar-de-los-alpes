"""Billeteras de los proveedores que la POC usa en sus demostraciones.

El paso de acreditación de la saga liquida al proveedor que OperacionesBC asigna.
Sin billetera esa acreditación falla de forma permanente y la saga terminaría
siempre EN_DISPUTA, que es justo el desenlace que se quiere poder distinguir.
Sembrarlas al arrancar equivale al alta contable que en producción ocurre cuando
el proveedor se homologa.

Solo se crean si no existen, así un cambio de estado o un saldo acumulado por la
API no se pierden al reiniciar el servicio.
"""

import logging
from collections.abc import Callable

from app.aplicacion.comandos import CrearBilleteraCommand, CrearBilleteraHandler
from app.aplicacion.puertos import UnidadDeTrabajo
from app.dominio.errores import BilleteraDuplicadaError
from app.infraestructura import contenedor

logger = logging.getLogger("wallet.semilla")

# `prov-hda-expert-01` es el proveedor que OperacionesBC asigna en la saga.
BILLETERAS_INICIALES: tuple[CrearBilleteraCommand, ...] = (
    CrearBilleteraCommand(proveedor_id="prov-hda-expert-01", moneda="COP"),
)


def sembrar_billeteras(
    fabrica_de_unidades: Callable[[], UnidadDeTrabajo] = contenedor.unidad_de_trabajo,
) -> None:
    for comando in BILLETERAS_INICIALES:
        with fabrica_de_unidades() as uow:
            if uow.billeteras.obtener_por_proveedor_id(comando.proveedor_id):
                continue
        try:
            CrearBilleteraHandler(
                fabrica_de_unidades(), contenedor.obtener_dispatcher()
            ).ejecutar(comando)
            logger.info("billetera sembrada para el proveedor %s", comando.proveedor_id)
        except BilleteraDuplicadaError:
            # Otra réplica la creó al mismo tiempo.
            logger.info("billetera de %s ya creada por otra instancia", comando.proveedor_id)
