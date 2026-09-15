from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CrearPagoRequestSchema(BaseModel):
    trabajo_id: str
    monto: Decimal
    moneda: str = Field(default="COP", min_length=3, max_length=3)
    referencia_externa: str = Field(min_length=1, max_length=120)
    sub_trabajo_id: str | None = None
    proveedor_id: str | None = None
    psp: str | None = Field(default=None, examples=["wompi-colombia"])


class PagoResponseSchema(BaseModel):
    id: str
    trabajo_id: str
    tipo: str
    sub_trabajo_id: str | None
    proveedor_id: str | None
    monto: Decimal
    moneda: str
    psp: str
    referencia_externa: str
    estado: str
    referencia_psp: str | None
    motivo: str | None
    fecha_creacion: datetime


class ErrorResponseSchema(BaseModel):
    detalle: str
