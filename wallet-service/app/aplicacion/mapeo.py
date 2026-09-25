from app.aplicacion.dtos import BilleteraDetalleDTO, BilleteraDTO, MovimientoDTO
from app.dominio.billetera import Billetera, Movimiento


def billetera_a_dto(billetera: Billetera) -> BilleteraDTO:
    return BilleteraDTO(
        id=str(billetera.id),
        proveedor_id=billetera.proveedor_id,
        saldo=billetera.saldo.monto,
        moneda=billetera.saldo.moneda,
        estado=billetera.estado.value,
    )


def billetera_a_detalle_dto(billetera: Billetera) -> BilleteraDetalleDTO:
    return BilleteraDetalleDTO(
        id=str(billetera.id),
        proveedor_id=billetera.proveedor_id,
        saldo=billetera.saldo.monto,
        moneda=billetera.saldo.moneda,
        estado=billetera.estado.value,
        fecha_creacion=billetera.fecha_creacion,
        total_movimientos=len(billetera.movimientos),
    )


def movimiento_a_dto(movimiento: Movimiento) -> MovimientoDTO:
    return MovimientoDTO(
        id=str(movimiento.id),
        tipo=movimiento.tipo.value,
        motivo=movimiento.motivo.value,
        monto=movimiento.monto.monto,
        saldo_resultante=movimiento.saldo_resultante.monto,
        fecha=movimiento.fecha,
        referencia_externa=movimiento.referencia_externa,
    )
