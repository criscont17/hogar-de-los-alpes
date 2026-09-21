from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.aplicacion.sagas.contratos_saga import SolicitudInicioSaga
from app.infraestructura import contenedor

router = APIRouter(prefix="/sagas", tags=["Sagas"])


class SolicitudActivarServicioSchema(BaseModel):
    cliente_id: str = Field(..., description="ID del cliente solicitante")
    descripcion: str = Field(..., description="Descripción del trabajo")
    pais: str = Field("CO", description="Código de país (ej. CO, MX)")
    ciudad: str = Field("Bogotá", description="Ciudad del servicio")
    direccion: str = Field("Calle 100 # 15-20", description="Dirección del servicio")
    moneda: str = Field("COP", description="Moneda (COP, MXN, USD)")
    monto_estimado: Decimal = Field(..., gt=0, description="Monto estimado del servicio")
    partner_id: str | None = Field(None, description="ID del partner si es canal B2B2C")
    referencia_externa: str | None = Field(None, description="Referencia propia del partner")
    simular_fallo_en_paso: str | None = Field(
        None, description="Simulación controlada para pruebas de fallo/compensación: 'PAGO' o 'OPERACIONES'"
    )


class RespuestaInicioSagaSchema(BaseModel):
    saga_id: UUID
    trabajo_id: UUID
    estado_global: str
    mensaje: str


@router.post(
    "/activar-servicio",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=RespuestaInicioSagaSchema,
    summary="Iniciar transacción distribuida (Saga) para activar un servicio",
)
def iniciar_saga_activar_servicio(solicitud: SolicitudActivarServicioSchema):
    trabajo_id = uuid4()
    solicitud_dominio = SolicitudInicioSaga(
        trabajo_id=trabajo_id,
        cliente_id=solicitud.cliente_id,
        descripcion=solicitud.descripcion,
        pais=solicitud.pais,
        ciudad=solicitud.ciudad,
        direccion=solicitud.direccion,
        moneda=solicitud.moneda,
        monto_estimado=solicitud.monto_estimado,
        partner_id=solicitud.partner_id,
        referencia_externa=solicitud.referencia_externa,
        simular_fallo_en_paso=solicitud.simular_fallo_en_paso,
    )

    orquestador = contenedor.obtener_orquestador_saga()
    saga_id = orquestador.iniciar_saga(solicitud_dominio)

    return RespuestaInicioSagaSchema(
        saga_id=saga_id,
        trabajo_id=trabajo_id,
        estado_global="INICIADA",
        mensaje="Saga distribuida iniciada exitosamente en GestionDeTrabajosBC",
    )


@router.get(
    "/{saga_id}",
    summary="Consultar estado y Saga Log de una transacción distribuida",
)
def consultar_saga(saga_id: UUID):
    repo = contenedor.obtener_saga_log_repo()
    instancia = repo.obtener_saga(saga_id)
    if not instancia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Saga con id {saga_id} no encontrada",
        )

    pasos = [
        {
            "paso_numero": p.paso_numero,
            "nombre_paso": p.nombre_paso,
            "servicio_participante": p.servicio_participante,
            "estado_paso": p.estado_paso,
            "comando_enviado": p.comando_enviado,
            "evento_recibido": p.evento_recibido,
            "error": p.error,
            "fecha_inicio": p.fecha_inicio.isoformat() if p.fecha_inicio else None,
            "fecha_fin": p.fecha_fin.isoformat() if p.fecha_fin else None,
        }
        for p in instancia.pasos
    ]

    return {
        "saga_id": str(instancia.saga_id),
        "tipo_saga": instancia.tipo_saga,
        "trabajo_id": str(instancia.trabajo_id),
        "estado_global": instancia.estado_global,
        "paso_actual": instancia.paso_actual,
        "error": instancia.error,
        "fecha_creacion": instancia.fecha_creacion.isoformat(),
        "fecha_actualizacion": instancia.fecha_actualizacion.isoformat(),
        "pasos": pasos,
    }


@router.get(
    "",
    summary="Listar transacciones distribuidas recientes",
)
def listar_sagas(limite: int = 20):
    repo = contenedor.obtener_saga_log_repo()
    instancias = repo.listar_sagas(limite=limite)
    return [
        {
            "saga_id": str(i.saga_id),
            "tipo_saga": i.tipo_saga,
            "trabajo_id": str(i.trabajo_id),
            "estado_global": i.estado_global,
            "paso_actual": i.paso_actual,
            "error": i.error,
            "fecha_creacion": i.fecha_creacion.isoformat(),
        }
        for i in instancias
    ]
