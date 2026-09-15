from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CondicionComercialSchema(BaseModel):
    tipo: str = Field(examples=["TOPE"])
    clave: str = Field(examples=["PLUS"])
    valor: Decimal = Field(examples=["4000000"])


class RegistrarPartnerRequestSchema(BaseModel):
    nombre: str
    pais: str = Field(min_length=2, max_length=2, examples=["CO"])
    red_de_proveedores: list[str] | None = None
    condiciones: list[CondicionComercialSchema]


class PartnerResponseSchema(BaseModel):
    partner_id: str
    nombre: str
    pais: str
    red_de_proveedores: list[str] | None
    condiciones: list[CondicionComercialSchema]
    tiene_adaptador: bool
    fecha_registro: datetime


class SaludPartnerResponseSchema(BaseModel):
    partner_id: str
    circuito: str
    fallos_consecutivos: int
    pendientes: int
    sincronizados: int
    degradaciones: int
    descartados: int
    ultimo_error: str | None
    core_disponible: bool


class SimularPartnerRequestSchema(BaseModel):
    disponible: bool
