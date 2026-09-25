from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.dominio.billetera import EstadoBilletera, MotivoMovimiento


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


class RetiroProveedorRequestSchema(BaseModel):
    """Retiro pedido por el proveedor. El motivo por omisión es el del caso de uso."""

    monto: Decimal = Field(gt=0)
    motivo: str = MotivoMovimiento.RETIRO_A_PROVEEDOR.value
    referencia_externa: str | None = None


class TrabajoLiquidadoRequestSchema(BaseModel):
    trabajo_id: UUID
    proveedor_id: UUID
    monto: Decimal
    moneda: str = Field(default="COP", min_length=3, max_length=3)


class CambiarEstadoBilleteraRequestSchema(BaseModel):
    """Única mutación admitida: el saldo solo se mueve con acreditar/debitar."""

    estado: EstadoBilletera


class BilleteraResponseSchema(BaseModel):
    id: str
    proveedor_id: str
    saldo: Decimal
    moneda: str
    estado: str


class BilleteraDetalleResponseSchema(BilleteraResponseSchema):
    fecha_creacion: datetime
    total_movimientos: int


class PaginaBilleterasResponseSchema(BaseModel):
    items: list[BilleteraDetalleResponseSchema]
    total: int
    limite: int
    desplazamiento: int


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
