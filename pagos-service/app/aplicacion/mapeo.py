from app.aplicacion.dtos import PagoDTO
from app.dominio.pago import Pago


def pago_a_dto(pago: Pago) -> PagoDTO:
    return PagoDTO(
        id=str(pago.id),
        trabajo_id=pago.trabajo_id,
        tipo=pago.tipo.value,
        sub_trabajo_id=pago.sub_trabajo_id,
        proveedor_id=pago.proveedor_id,
        monto=pago.monto.monto,
        moneda=pago.monto.moneda,
        psp=pago.psp,
        referencia_externa=pago.referencia_externa,
        estado=pago.estado.value,
        referencia_psp=pago.referencia_psp,
        motivo=pago.motivo,
        fecha_creacion=pago.fecha_creacion,
    )
