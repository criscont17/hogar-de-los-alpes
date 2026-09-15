"""Contrato público (Published Language) de GestionDeTrabajosBC.

Estas clases son independientes de los eventos de dominio a propósito: renombrar un campo
interno no debe romper a OperacionesBC, Pagos, Crédito ni a los partners. El sufijo de
versión permite publicar un esquema nuevo sin dejar de emitir el anterior; la política es
mantener como máximo dos versiones activas por evento (la vigente y la deprecada) hasta
que los consumidores migren.
"""

from .asignacion_rechazada_v1 import AsignacionRechazadaV1
from .creacion_de_trabajo_rechazada_v1 import CreacionDeTrabajoRechazadaV1
from .evento_de_integracion_de_trabajo import EventoDeIntegracionDeTrabajo
from .proveedor_asignado_v1 import ProveedorAsignadoV1
from .sub_trabajo_completado_v1 import SubTrabajoCompletadoV1
from .sub_trabajo_desbloqueado_v1 import SubTrabajoDesbloqueadoV1
from .sub_trabajo_iniciado_v1 import SubTrabajoIniciadoV1
from .trabajo_cancelado_v1 import TrabajoCanceladoV1
from .trabajo_cerrado_v1 import TrabajoCerradoV1
from .trabajo_creado_v1 import TrabajoCreadoV1
from .trabajo_creado_v2 import TrabajoCreadoV2
from .trabajo_rediagnosticado_v1 import TrabajoRediagnosticadoV1

__all__ = [
    "AsignacionRechazadaV1",
    "CreacionDeTrabajoRechazadaV1",
    "EventoDeIntegracionDeTrabajo",
    "ProveedorAsignadoV1",
    "SubTrabajoCompletadoV1",
    "SubTrabajoDesbloqueadoV1",
    "SubTrabajoIniciadoV1",
    "TrabajoCanceladoV1",
    "TrabajoCerradoV1",
    "TrabajoCreadoV1",
    "TrabajoCreadoV2",
    "TrabajoRediagnosticadoV1",
]
