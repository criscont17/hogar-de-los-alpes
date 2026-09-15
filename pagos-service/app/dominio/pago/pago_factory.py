from app.dominio.pago.eventos import PagoCreado

from .dinero import Dinero
from .enums import EstadoPago, TipoPago
from .identificadores import PagoId
from .pago import Pago


class PagoFactory:
    """Único punto de creación de `Pago`: garantiza que nace con el evento
    `PagoCreado` ya encolado, sin importar quién invoque la fábrica (la API de
    checkout o el consumidor del evento `TrabajoCerradoV1`)."""

    @staticmethod
    def crear(
        *,
        trabajo_id: str,
        tipo: TipoPago,
        monto: Dinero,
        psp: str,
        referencia_externa: str,
        sub_trabajo_id: str | None = None,
        proveedor_id: str | None = None,
    ) -> Pago:
        pago = Pago(
            id=PagoId.nuevo(),
            trabajo_id=trabajo_id,
            tipo=tipo,
            monto=monto,
            psp=psp,
            referencia_externa=referencia_externa,
            estado=EstadoPago.PENDIENTE,
            sub_trabajo_id=sub_trabajo_id,
            proveedor_id=proveedor_id,
        )
        pago.add_domain_event(
            PagoCreado(
                pago_id=str(pago.id),
                trabajo_id=pago.trabajo_id,
                sub_trabajo_id=pago.sub_trabajo_id,
                proveedor_id=pago.proveedor_id,
                tipo=pago.tipo.value,
                monto=pago.monto.monto,
                moneda=pago.monto.moneda,
                psp=pago.psp,
                referencia_externa=pago.referencia_externa,
            )
        )
        return pago
