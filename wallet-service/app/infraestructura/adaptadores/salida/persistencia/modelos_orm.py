from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid
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


class EventoSalienteModel(Base):
    """Bandeja de salida: un evento de integración a la espera de ser publicado.

    Se escribe en la misma transacción que el movimiento que lo produjo, así que
    la fila existe si y solo si el hecho quedó confirmado. El relay la lee después
    y la marca `PUBLICADO` cuando el broker confirma la entrega.
    """

    __tablename__ = "eventos_salientes"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    # Identidad del evento de integración: viaja en el sobre para que el consumidor
    # descarte duplicados si el relay llega a publicar dos veces el mismo hecho.
    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, nullable=False, index=True
    )
    tipo: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    clave_particion: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # PENDIENTE (por publicar) | PUBLICADO (entregado) | FALLIDO (agotó intentos)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # Marca el backoff: hasta esta fecha el relay no vuelve a intentar la entrega.
    disponible_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fecha_publicacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
