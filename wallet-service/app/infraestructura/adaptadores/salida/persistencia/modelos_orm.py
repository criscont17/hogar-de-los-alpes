from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class BilleteraModel(Base):
    __tablename__ = "billeteras"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    proveedor_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    saldo_monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    saldo_moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    movimientos: Mapped[list["MovimientoModel"]] = relationship(
        back_populates="billetera",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MovimientoModel.fecha",
    )


class MovimientoModel(Base):
    __tablename__ = "movimientos"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    billetera_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("billeteras.id"), nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    motivo: Mapped[str] = mapped_column(String(30), nullable=False)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    saldo_resultante: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    referencia_externa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    billetera: Mapped[BilleteraModel] = relationship(back_populates="movimientos")
