from app.aplicacion.comandos import CrearPagoCommand
from app.aplicacion.dtos import PagoDTO
from app.aplicacion.queries import ListarPagosQuery, ObtenerPagoQuery
from app.dominio.pago import TipoPago

from .schemas import CrearPagoRequestSchema, PagoResponseSchema


def a_comando_crear(schema: CrearPagoRequestSchema) -> CrearPagoCommand:
    return CrearPagoCommand(
        trabajo_id=schema.trabajo_id,
        tipo=TipoPago.COBRO_CLIENTE.value,
        monto=schema.monto,
        moneda=schema.moneda,
        referencia_externa=schema.referencia_externa,
        sub_trabajo_id=schema.sub_trabajo_id,
        proveedor_id=schema.proveedor_id,
        psp=schema.psp,
    )


def a_query_pago(pago_id: str) -> ObtenerPagoQuery:
    return ObtenerPagoQuery(pago_id)


def a_query_listar(trabajo_id: str | None, limite: int) -> ListarPagosQuery:
    return ListarPagosQuery(trabajo_id=trabajo_id, limite=limite)


def a_schema_pago(dto: PagoDTO) -> PagoResponseSchema:
    return PagoResponseSchema(
        id=dto.id,
        trabajo_id=dto.trabajo_id,
        tipo=dto.tipo,
        sub_trabajo_id=dto.sub_trabajo_id,
        proveedor_id=dto.proveedor_id,
        monto=dto.monto,
        moneda=dto.moneda,
        psp=dto.psp,
        referencia_externa=dto.referencia_externa,
        estado=dto.estado,
        referencia_psp=dto.referencia_psp,
        motivo=dto.motivo,
        fecha_creacion=dto.fecha_creacion,
    )
