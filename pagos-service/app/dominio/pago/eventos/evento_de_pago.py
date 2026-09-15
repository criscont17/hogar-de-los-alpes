from dataclasses import dataclass

from app.seedwork.dominio import DomainEvent


@dataclass(frozen=True, kw_only=True)
class EventoDePago(DomainEvent):
    """Base de los hechos del agregado `Pago`.

    Lleva la referencia al trabajo (y, si aplica, al sub-trabajo y al proveedor)
    para que un suscriptor pueda enrutar el hecho sin volver a cargar el agregado.
    """

    pago_id: str
    trabajo_id: str
    sub_trabajo_id: str | None = None
    proveedor_id: str | None = None
