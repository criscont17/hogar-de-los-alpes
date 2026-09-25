from dataclasses import dataclass
from decimal import Decimal

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EventoDeTrabajo(DomainEvent):
    """Base de los hechos del agregado `Trabajo`.

    Lleva el origen del trabajo para que un suscriptor pueda enrutar el hecho
    (por ejemplo, sincronizarlo con el partner que lo creó) sin volver a cargar
    el agregado. En trabajos de Marketplace ambos campos quedan en `None`.
    """

    trabajo_id: str
    partner_id: str | None = None
    referencia_externa: str | None = None


@dataclass(frozen=True)
class DetalleSubTrabajo:
    sub_trabajo_id: str
    categoria: str
    estado: str
    depende_de: tuple[str, ...]


@dataclass(frozen=True)
class Liquidacion:
    """Lo que se le debe a un proveedor por un sub-trabajo completado."""

    sub_trabajo_id: str
    proveedor_id: str
    monto: Decimal
