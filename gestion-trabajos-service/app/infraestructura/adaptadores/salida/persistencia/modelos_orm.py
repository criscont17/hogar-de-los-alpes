from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class TrabajoModel(Base):
    __tablename__ = "trabajos"
    __table_args__ = (
        # Un partner no puede tener dos trabajos con la misma referencia propia. En
        # trabajos de Marketplace ambas columnas son NULL y no chocan entre sí.
        UniqueConstraint("partner_id", "referencia_externa", name="uq_trabajos_referencia_partner"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    canal: Mapped[str] = mapped_column(String(20), nullable=False)
    partner_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    referencia_externa: Mapped[str | None] = mapped_column(String(120), nullable=True)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    urgencia: Mapped[str] = mapped_column(String(20), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(120), nullable=False)
    direccion: Mapped[str] = mapped_column(String(255), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    monto_maximo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    proveedores_permitidos: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sla_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sub_trabajos: Mapped[list["SubTrabajoModel"]] = relationship(
        back_populates="trabajo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="SubTrabajoModel.orden",
    )

    # Bloqueo optimista: si otra operación guardó el trabajo entre la lectura y
    # la escritura, el UPDATE no encuentra la versión esperada y falla.
    __mapper_args__ = {"version_id_col": version}


class SubTrabajoModel(Base):
    __tablename__ = "sub_trabajos"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    trabajo_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("trabajos.id"), nullable=False, index=True
    )
    orden: Mapped[int] = mapped_column(Integer, nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    depende_de: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    proveedor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monto_cotizado: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    evidencias: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    trabajo: Mapped[TrabajoModel] = relationship(back_populates="sub_trabajos")
