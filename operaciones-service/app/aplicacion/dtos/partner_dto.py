from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class CondicionComercialDTO:
    tipo: str
    clave: str
    valor: Decimal


@dataclass(frozen=True)
class PartnerDTO:
    partner_id: str
    nombre: str
    pais: str
    red_de_proveedores: tuple[str, ...] | None
    condiciones: tuple[CondicionComercialDTO, ...]
    tiene_adaptador: bool
    fecha_registro: datetime


@dataclass(frozen=True)
class RegistroDePartnerDTO:
    partner: PartnerDTO
    creado: bool
