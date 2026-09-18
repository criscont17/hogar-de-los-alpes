from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

# Comandos
COMANDO_AUTORIZAR_PAGO = "AutorizarPagoTrabajoV1"
COMANDO_REVERTIR_PAGO = "RevertirPagoTrabajoV1"
COMANDO_ASIGNAR_PROVEEDOR = "AsignarProveedorTrabajoV1"
COMANDO_LIBERAR_ASIGNACION = "LiberarAsignacionProveedorV1"

# Eventos de respuesta
EVENTO_PAGO_AUTORIZADO = "PagoTrabajoAutorizadoV1"
EVENTO_PAGO_RECHAZADO = "PagoTrabajoRechazadoV1"
EVENTO_PAGO_REVERTIDO = "PagoTrabajoRevertidoV1"

EVENTO_PROVEEDOR_ASIGNADO = "ProveedorTrabajoAsignadoV1"
EVENTO_ASIGNACION_RECHAZADA = "AsignacionProveedorRechazadaV1"
EVENTO_ASIGNACION_LIBERADA = "AsignacionProveedorLiberadaV1"


@dataclass(frozen=True)
class SolicitudInicioSaga:
    trabajo_id: UUID
    cliente_id: str
    descripcion: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    monto_estimado: Decimal
    partner_id: str | None = None
    referencia_externa: str | None = None
    simular_fallo_en_paso: str | None = None  # "PAGO" | "OPERACIONES" para pruebas de compensación


def serializar_comando(tipo_comando: str, saga_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_type": tipo_comando,
        "saga_id": str(saga_id),
        "payload": payload,
    }
