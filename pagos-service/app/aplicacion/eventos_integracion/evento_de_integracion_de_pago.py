from dataclasses import dataclass

from app.seedwork.aplicacion import IntegrationEvent


@dataclass(frozen=True, kw_only=True)
class EventoDeIntegracionDePago(IntegrationEvent):
    """Campos comunes a todo evento público de un pago.

    `proveedor_id` permite a WalletBC relacionar el hecho con la billetera a
    acreditar sin tener que consultar de vuelta a PagosBC.
    """

    pago_id: str
    trabajo_id: str
    sub_trabajo_id: str | None = None
    proveedor_id: str | None = None
