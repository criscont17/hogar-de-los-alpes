from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

# Comandos
COMANDO_AUTORIZAR_PAGO = "AutorizarPagoTrabajoV1"
COMANDO_REVERTIR_PAGO = "RevertirPagoTrabajoV1"
COMANDO_ASIGNAR_PROVEEDOR = "AsignarProveedorTrabajoV1"
COMANDO_LIBERAR_ASIGNACION = "LiberarAsignacionProveedorV1"
COMANDO_ACREDITAR_PROVEEDOR = "AcreditarProveedorV1"

# Eventos de respuesta
EVENTO_PAGO_AUTORIZADO = "PagoTrabajoAutorizadoV1"
EVENTO_PAGO_RECHAZADO = "PagoTrabajoRechazadoV1"
EVENTO_PAGO_REVERTIDO = "PagoTrabajoRevertidoV1"

EVENTO_PROVEEDOR_ASIGNADO = "ProveedorTrabajoAsignadoV1"
EVENTO_ASIGNACION_RECHAZADA = "AsignacionProveedorRechazadaV1"
EVENTO_ASIGNACION_LIBERADA = "AsignacionProveedorLiberadaV1"
EVENTO_EJECUCION_COMPLETADA = "EjecucionTrabajoCompletadaV1"
EVENTO_EJECUCION_FALLIDA = "EjecucionTrabajoFallidaV1"

EVENTO_WALLET_ACREDITADA = "WalletAcreditadaV1"
EVENTO_ACREDITACION_FALLIDA = "AcreditacionFallidaV1"

# Pasos de la saga. El número es la clave con la que el Saga Log correlaciona el
# inicio, el fin y la compensación de cada paso.
PASO_CREAR_TRABAJO = 1
PASO_AUTORIZAR_PAGO = 2
PASO_ASIGNAR_PROVEEDOR = 3
PASO_EJECUTAR_TRABAJO = 4
PASO_ACREDITAR_PROVEEDOR = 5

# Fallos que se pueden forzar desde la solicitud para demostrar cada desenlace.
FALLO_EN_PAGO = "PAGO"
FALLO_EN_OPERACIONES = "OPERACIONES"
FALLO_EN_EJECUCION = "EJECUCION"
FALLO_EN_WALLET = "WALLET"
FALLOS_SIMULABLES = (
    FALLO_EN_PAGO,
    FALLO_EN_OPERACIONES,
    FALLO_EN_EJECUCION,
    FALLO_EN_WALLET,
)


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
    # "PAGO" | "OPERACIONES" | "EJECUCION" | "WALLET": fuerza el fallo de ese paso
    # para demostrar su compensación (o la disputa, en el caso de WALLET).
    simular_fallo_en_paso: str | None = None


def serializar_comando(tipo_comando: str, saga_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "command_type": tipo_comando,
        "saga_id": str(saga_id),
        "payload": payload,
    }
