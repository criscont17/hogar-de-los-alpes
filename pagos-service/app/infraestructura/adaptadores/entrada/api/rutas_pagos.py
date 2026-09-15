from fastapi import APIRouter, Depends, Query, status

from app.aplicacion.comandos import CrearPagoHandler
from app.aplicacion.queries import ListarPagosHandler, ObtenerPagoHandler

from .dependencias import obtener_crear_handler, obtener_listar_handler, obtener_pago_handler
from .mappers import a_comando_crear, a_query_listar, a_query_pago, a_schema_pago
from .schemas import CrearPagoRequestSchema, PagoResponseSchema

router = APIRouter(prefix="/pagos", tags=["Pagos"])


@router.post("", response_model=PagoResponseSchema, status_code=status.HTTP_201_CREATED)
def crear_pago(
    schema: CrearPagoRequestSchema,
    handler: CrearPagoHandler = Depends(obtener_crear_handler),
) -> PagoResponseSchema:
    """Checkout del cliente: cobra un trabajo contra el PSP de su moneda.

    Idempotente por `referencia_externa`: reintentar la misma solicitud nunca
    duplica el cobro.
    """

    return a_schema_pago(handler.ejecutar(a_comando_crear(schema)))


@router.get("", response_model=list[PagoResponseSchema])
def listar_pagos(
    trabajo_id: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    handler: ListarPagosHandler = Depends(obtener_listar_handler),
) -> list[PagoResponseSchema]:
    dtos = handler.ejecutar(a_query_listar(trabajo_id, limite))
    return [a_schema_pago(dto) for dto in dtos]


@router.get("/{pago_id}", response_model=PagoResponseSchema)
def obtener_pago(
    pago_id: str,
    handler: ObtenerPagoHandler = Depends(obtener_pago_handler),
) -> PagoResponseSchema:
    return a_schema_pago(handler.ejecutar(a_query_pago(pago_id)))
