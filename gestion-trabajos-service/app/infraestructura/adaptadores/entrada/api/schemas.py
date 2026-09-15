from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class UbicacionSchema(BaseModel):
    pais: str = Field(min_length=2, max_length=2, examples=["CO"])
    ciudad: str
    direccion: str


class SubTrabajoSolicitadoSchema(BaseModel):
    clave: str = Field(min_length=1, max_length=60, examples=["plomeria"])
    categoria: str = Field(examples=["Plomeria"])
    descripcion: str
    depende_de: list[str] = Field(default_factory=list)


class CrearTrabajoRequestSchema(BaseModel):
    descripcion: str
    urgencia: str = Field(examples=["Alta"])
    ubicacion: UbicacionSchema
    moneda: str = Field(default="COP", min_length=3, max_length=3)
    sub_trabajos: list[SubTrabajoSolicitadoSchema]


class AsignarProveedorRequestSchema(BaseModel):
    proveedor_id: UUID
    monto_cotizado: Decimal


class CompletarSubTrabajoRequestSchema(BaseModel):
    evidencias: list[str] = Field(default_factory=list)


class RegistrarRediagnosticoRequestSchema(BaseModel):
    hallazgo: str
    categoria: str
    descripcion: str
    bloquea_a: list[str] = Field(default_factory=list)


class CancelarTrabajoRequestSchema(BaseModel):
    motivo: str


class SubTrabajoResponseSchema(BaseModel):
    id: str
    categoria: str
    descripcion: str
    estado: str
    depende_de: list[str]
    proveedor_id: str | None
    monto_cotizado: Decimal | None
    evidencias: list[str]


class TrabajoResponseSchema(BaseModel):
    id: str
    canal: str
    partner_id: str | None
    referencia_externa: str | None
    descripcion: str
    urgencia: str
    pais: str
    ciudad: str
    direccion: str
    moneda: str
    estado: str
    costo_total: Decimal
    monto_maximo: Decimal | None
    sla_horas: int | None
    fecha_creacion: datetime
    sub_trabajos: list[SubTrabajoResponseSchema]


class ErrorResponseSchema(BaseModel):
    detalle: str
