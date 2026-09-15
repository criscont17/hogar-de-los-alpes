from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class PartnerModel(Base):
    __tablename__ = "partners"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    pais: Mapped[str] = mapped_column(String(2), nullable=False)
    red_de_proveedores: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    condiciones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    fecha_registro: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TrabajoDePartnerModel(Base):
    """Vista de cada trabajo de un partner, alimentada por los eventos de GestionDeTrabajosBC."""

    __tablename__ = "trabajos_de_partner"

    partner_id: Mapped[str] = mapped_column(String(60), primary_key=True)
    referencia_externa: Mapped[str] = mapped_column(String(120), primary_key=True)
    estado: Mapped[str] = mapped_column(String(20), nullable=False)
    trabajo_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    moneda: Mapped[str | None] = mapped_column(String(3), nullable=True)
    monto_maximo: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    sla_horas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    costo_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_trabajos: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    fecha_solicitud: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fecha_actualizacion: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
