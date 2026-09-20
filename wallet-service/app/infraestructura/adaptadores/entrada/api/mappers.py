from app.aplicacion.comandos import (
    AcreditarSaldoCommand,
    CambiarEstadoBilleteraCommand,
    CrearBilleteraCommand,
    DebitarSaldoCommand,
    EliminarBilleteraCommand,
    ProcesarTrabajoLiquidadoCommand,
)
from app.aplicacion.dtos import (
    BilleteraDetalleDTO,
    BilleteraDTO,
    MovimientoDTO,
    PaginaBilleterasDTO,
)
from app.aplicacion.queries import (
    ListarBilleterasQuery,
    ListarMovimientosQuery,
    ObtenerBilleteraQuery,
    ObtenerMovimientoQuery,
    ObtenerSaldoQuery,
)

from .schemas import (
    AcreditarSaldoRequestSchema,
    BilleteraDetalleResponseSchema,
    BilleteraResponseSchema,
    CambiarEstadoBilleteraRequestSchema,
    CrearBilleteraRequestSchema,
    DebitarSaldoRequestSchema,
    MovimientoResponseSchema,
    PaginaBilleterasResponseSchema,
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


def a_comando_cambiar_estado(
    billetera_id: str, schema: CambiarEstadoBilleteraRequestSchema
) -> CambiarEstadoBilleteraCommand:
    return CambiarEstadoBilleteraCommand(billetera_id, schema.estado.value)


def a_comando_eliminar(billetera_id: str) -> EliminarBilleteraCommand:
    return EliminarBilleteraCommand(billetera_id)


def a_query_saldo(billetera_id: str) -> ObtenerSaldoQuery:
    return ObtenerSaldoQuery(billetera_id)


def a_query_billetera(billetera_id: str) -> ObtenerBilleteraQuery:
    return ObtenerBilleteraQuery(billetera_id)


def a_query_billeteras(
    estado: str | None = None,
    proveedor_id: str | None = None,
    limite: int = 50,
    desplazamiento: int = 0,
) -> ListarBilleterasQuery:
    return ListarBilleterasQuery(estado, proveedor_id, limite, desplazamiento)


def a_query_movimiento(billetera_id: str, movimiento_id: str) -> ObtenerMovimientoQuery:
    return ObtenerMovimientoQuery(billetera_id, movimiento_id)


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


def a_schema_billetera_detalle(dto: BilleteraDetalleDTO) -> BilleteraDetalleResponseSchema:
    return BilleteraDetalleResponseSchema(
        id=dto.id,
        proveedor_id=dto.proveedor_id,
        saldo=dto.saldo,
        moneda=dto.moneda,
        estado=dto.estado,
        fecha_creacion=dto.fecha_creacion,
        total_movimientos=dto.total_movimientos,
    )


def a_schema_pagina_billeteras(dto: PaginaBilleterasDTO) -> PaginaBilleterasResponseSchema:
    return PaginaBilleterasResponseSchema(
        items=[a_schema_billetera_detalle(item) for item in dto.items],
        total=dto.total,
        limite=dto.limite,
        desplazamiento=dto.desplazamiento,
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
