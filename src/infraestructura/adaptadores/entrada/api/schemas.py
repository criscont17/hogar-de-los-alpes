from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CrearBilleteraRequestSchema(BaseModel):
    proveedor_id: UUID
    moneda: str = Field(default="COP", min_length=3, max_length=3)


class AcreditarSaldoRequestSchema(BaseModel):
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None


class DebitarSaldoRequestSchema(BaseModel):
    monto: Decimal
    motivo: str
    referencia_externa: str | None = None


class TrabajoLiquidadoRequestSchema(BaseModel):
    trabajo_id: UUID
    proveedor_id: UUID
    monto: Decimal
    moneda: str = Field(default="COP", min_length=3, max_length=3)


class BilleteraResponseSchema(BaseModel):
    id: str
    proveedor_id: str
    saldo: Decimal
    moneda: str
    estado: str


class MovimientoResponseSchema(BaseModel):
    id: str
    tipo: str
    motivo: str
    monto: Decimal
    saldo_resultante: Decimal
    fecha: datetime
    referencia_externa: str | None


class ErrorResponseSchema(BaseModel):
    detalle: str
