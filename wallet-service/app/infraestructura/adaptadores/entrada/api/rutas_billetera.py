from datetime import datetime

from fastapi import APIRouter, Depends, Query, status

from app.aplicacion.comandos import (
    AcreditarSaldoHandler,
    CambiarEstadoBilleteraHandler,
    CrearBilleteraHandler,
    DebitarSaldoHandler,
    EliminarBilleteraHandler,
    ProcesarTrabajoLiquidadoHandler,
)
from app.aplicacion.queries import (
    ListarBilleterasHandler,
    ListarMovimientosHandler,
    ObtenerBilleteraHandler,
    ObtenerMovimientoHandler,
    ObtenerSaldoHandler,
)

from .dependencias import (
    obtener_acreditar_handler,
    obtener_billetera_handler,
    obtener_cambiar_estado_handler,
    obtener_crear_handler,
    obtener_debitar_handler,
    obtener_eliminar_handler,
    obtener_listar_billeteras_handler,
    obtener_movimiento_handler,
    obtener_movimientos_handler,
    obtener_saldo_handler,
    obtener_trabajo_liquidado_handler,
)
from .mappers import (
    a_comando_acreditar,
    a_comando_cambiar_estado,
    a_comando_crear,
    a_comando_debitar,
    a_comando_eliminar,
    a_comando_trabajo_liquidado,
    a_query_billetera,
    a_query_billeteras,
    a_query_movimiento,
    a_query_movimientos,
    a_query_saldo,
    a_schema_billetera,
    a_schema_billetera_detalle,
    a_schema_movimiento,
    a_schema_pagina_billeteras,
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


@router.get("/billeteras", response_model=PaginaBilleterasResponseSchema)
def listar_billeteras(
    estado: str | None = Query(default=None),
    proveedor_id: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    desplazamiento: int = Query(default=0, ge=0),
    handler: ListarBilleterasHandler = Depends(obtener_listar_billeteras_handler),
) -> PaginaBilleterasResponseSchema:
    return a_schema_pagina_billeteras(
        handler.ejecutar(a_query_billeteras(estado, proveedor_id, limite, desplazamiento))
    )


@router.get("/billeteras/{billetera_id}", response_model=BilleteraDetalleResponseSchema)
def obtener_billetera(
    billetera_id: str,
    handler: ObtenerBilleteraHandler = Depends(obtener_billetera_handler),
) -> BilleteraDetalleResponseSchema:
    return a_schema_billetera_detalle(handler.ejecutar(a_query_billetera(billetera_id)))


@router.patch("/billeteras/{billetera_id}", response_model=BilleteraDetalleResponseSchema)
def cambiar_estado_billetera(
    billetera_id: str,
    schema: CambiarEstadoBilleteraRequestSchema,
    handler: CambiarEstadoBilleteraHandler = Depends(obtener_cambiar_estado_handler),
) -> BilleteraDetalleResponseSchema:
    return a_schema_billetera_detalle(
        handler.ejecutar(a_comando_cambiar_estado(billetera_id, schema))
    )


@router.delete("/billeteras/{billetera_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_billetera(
    billetera_id: str,
    handler: EliminarBilleteraHandler = Depends(obtener_eliminar_handler),
) -> None:
    handler.ejecutar(a_comando_eliminar(billetera_id))


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


@router.get(
    "/billeteras/{billetera_id}/movimientos/{movimiento_id}",
    response_model=MovimientoResponseSchema,
)
def obtener_movimiento(
    billetera_id: str,
    movimiento_id: str,
    handler: ObtenerMovimientoHandler = Depends(obtener_movimiento_handler),
) -> MovimientoResponseSchema:
    return a_schema_movimiento(
        handler.ejecutar(a_query_movimiento(billetera_id, movimiento_id))
    )


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
