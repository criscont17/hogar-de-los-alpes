from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class PagoModel(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        # Idempotencia: la misma referencia externa (checkout, o trabajo+sub-trabajo
        # en una liquidación) nunca produce dos pagos.
        UniqueConstraint("referencia_externa", name="uq_pagos_referencia_externa"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    trabajo_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    sub_trabajo_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
    proveedor_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    psp: Mapped[str] = mapped_column(String(40), nullable=False)
    referencia_externa: Mapped[str] = mapped_column(String(120), nullable=False)
    estado: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    referencia_psp: Mapped[str | None] = mapped_column(String(120), nullable=True)
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Bloqueo optimista: si otra operación guardó el pago entre la lectura y la
    # escritura (por ejemplo, dos reentregas concurrentes de Pulsar), el UPDATE
    # no encuentra la versión esperada y falla.
    __mapper_args__ = {"version_id_col": version}
