from aplicacion.comandos import (
    AcreditarSaldoCommand,
    CrearBilleteraCommand,
    DebitarSaldoCommand,
    ProcesarTrabajoLiquidadoCommand,
)
from aplicacion.dtos import BilleteraDTO, MovimientoDTO
from aplicacion.queries import ListarMovimientosQuery, ObtenerSaldoQuery

from .schemas import (
    AcreditarSaldoRequestSchema,
    BilleteraResponseSchema,
    CrearBilleteraRequestSchema,
    DebitarSaldoRequestSchema,
    MovimientoResponseSchema,
    TrabajoLiquidadoRequestSchema,
)


def a_comando_crear(schema: CrearBilleteraRequestSchema) -> CrearBilleteraCommand:
    return CrearBilleteraCommand(str(schema.proveedor_id), schema.moneda)


def a_comando_acreditar(
    billetera_id: str, schema: AcreditarSaldoRequestSchema
) -> AcreditarSaldoCommand:
    return AcreditarSaldoCommand(
        billetera_id, schema.monto, schema.motivo, schema.referencia_externa
    )


def a_comando_debitar(
    billetera_id: str, schema: DebitarSaldoRequestSchema
) -> DebitarSaldoCommand:
    return DebitarSaldoCommand(
        billetera_id, schema.monto, schema.motivo, schema.referencia_externa
    )


def a_comando_trabajo_liquidado(
    schema: TrabajoLiquidadoRequestSchema,
) -> ProcesarTrabajoLiquidadoCommand:
    return ProcesarTrabajoLiquidadoCommand(
        trabajo_id=str(schema.trabajo_id),
        proveedor_id=str(schema.proveedor_id),
        monto=schema.monto,
        moneda=schema.moneda,
    )


def a_query_saldo(billetera_id: str) -> ObtenerSaldoQuery:
    return ObtenerSaldoQuery(billetera_id)


def a_query_movimientos(
    billetera_id: str,
    fecha_desde=None,
    fecha_hasta=None,
    tipo: str | None = None,
) -> ListarMovimientosQuery:
    return ListarMovimientosQuery(billetera_id, fecha_desde, fecha_hasta, tipo)


def a_schema_billetera(dto: BilleteraDTO) -> BilleteraResponseSchema:
    return BilleteraResponseSchema(
        id=dto.id,
        proveedor_id=dto.proveedor_id,
        saldo=dto.saldo,
        moneda=dto.moneda,
        estado=dto.estado,
    )


def a_schema_movimiento(dto: MovimientoDTO) -> MovimientoResponseSchema:
    return MovimientoResponseSchema(
        id=dto.id,
        tipo=dto.tipo,
        motivo=dto.motivo,
        monto=dto.monto,
        saldo_resultante=dto.saldo_resultante,
        fecha=dto.fecha,
        referencia_externa=dto.referencia_externa,
    )
