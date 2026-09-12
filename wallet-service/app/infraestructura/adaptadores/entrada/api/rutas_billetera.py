from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.aplicacion.comandos import (
    AcreditarSaldoHandler,
    CrearBilleteraHandler,
    DebitarSaldoHandler,
    ProcesarTrabajoLiquidadoHandler,
)
from app.aplicacion.queries import ListarMovimientosHandler, ObtenerSaldoHandler

from .dependencias import (
    obtener_acreditar_handler,
    obtener_crear_handler,
    obtener_debitar_handler,
    obtener_movimientos_handler,
    obtener_saldo_handler,
    obtener_trabajo_liquidado_handler,
)
from .mappers import (
    a_comando_acreditar,
    a_comando_crear,
    a_comando_debitar,
    a_comando_trabajo_liquidado,
    a_query_movimientos,
    a_query_saldo,
    a_schema_billetera,
    a_schema_movimiento,
)
from .schemas import (
    AcreditarSaldoRequestSchema,
    BilleteraResponseSchema,
    CrearBilleteraRequestSchema,
    DebitarSaldoRequestSchema,
    MovimientoResponseSchema,
    TrabajoLiquidadoRequestSchema,
)

router = APIRouter()


@router.post(
    "/billeteras",
    response_model=BilleteraResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def crear_billetera(
    schema: CrearBilleteraRequestSchema,
    handler: CrearBilleteraHandler = Depends(obtener_crear_handler),
) -> BilleteraResponseSchema:
    return a_schema_billetera(handler.ejecutar(a_comando_crear(schema)))


@router.get("/billeteras/{billetera_id}/saldo", response_model=BilleteraResponseSchema)
def obtener_saldo(
    billetera_id: str,
    handler: ObtenerSaldoHandler = Depends(obtener_saldo_handler),
) -> BilleteraResponseSchema:
    return a_schema_billetera(handler.ejecutar(a_query_saldo(billetera_id)))


@router.post("/billeteras/{billetera_id}/acreditar", response_model=BilleteraResponseSchema)
def acreditar_saldo(
    billetera_id: str,
    schema: AcreditarSaldoRequestSchema,
    handler: AcreditarSaldoHandler = Depends(obtener_acreditar_handler),
) -> BilleteraResponseSchema:
    return a_schema_billetera(handler.ejecutar(a_comando_acreditar(billetera_id, schema)))


@router.post("/billeteras/{billetera_id}/debitar", response_model=BilleteraResponseSchema)
def debitar_saldo(
    billetera_id: str,
    schema: DebitarSaldoRequestSchema,
    handler: DebitarSaldoHandler = Depends(obtener_debitar_handler),
) -> BilleteraResponseSchema:
    return a_schema_billetera(handler.ejecutar(a_comando_debitar(billetera_id, schema)))


@router.get(
    "/billeteras/{billetera_id}/movimientos",
    response_model=list[MovimientoResponseSchema],
)
def listar_movimientos(
    billetera_id: str,
    fecha_desde: datetime | None = Query(default=None),
    fecha_hasta: datetime | None = Query(default=None),
    tipo: str | None = Query(default=None),
    handler: ListarMovimientosHandler = Depends(obtener_movimientos_handler),
) -> list[MovimientoResponseSchema]:
    dtos = handler.ejecutar(
        a_query_movimientos(billetera_id, fecha_desde, fecha_hasta, tipo)
    )
    return [a_schema_movimiento(dto) for dto in dtos]


@router.post(
    "/eventos-externos/trabajo-liquidado",
    response_model=BilleteraResponseSchema,
)
def procesar_trabajo_liquidado(
    schema: TrabajoLiquidadoRequestSchema,
    handler: ProcesarTrabajoLiquidadoHandler = Depends(
        obtener_trabajo_liquidado_handler
    ),
) -> BilleteraResponseSchema:
    return a_schema_billetera(
        handler.ejecutar(a_comando_trabajo_liquidado(schema))
    )
