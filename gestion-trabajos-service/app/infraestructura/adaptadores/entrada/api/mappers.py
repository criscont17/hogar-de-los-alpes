from app.aplicacion.comandos import (
    AsignarProveedorCommand,
    CancelarTrabajoCommand,
    CerrarTrabajoCommand,
    CompletarSubTrabajoCommand,
    CrearTrabajoCommand,
    IniciarSubTrabajoCommand,
    RegistrarRediagnosticoCommand,
)
from app.aplicacion.dtos import SubTrabajoDTO, SubTrabajoSolicitado, TrabajoDTO
from app.aplicacion.queries import ListarTrabajosQuery, ObtenerTrabajoQuery

from .schemas import (
    AsignarProveedorRequestSchema,
    CancelarTrabajoRequestSchema,
    CompletarSubTrabajoRequestSchema,
    CrearTrabajoRequestSchema,
    RegistrarRediagnosticoRequestSchema,
    SubTrabajoResponseSchema,
    TrabajoResponseSchema,
)


def a_comando_crear(schema: CrearTrabajoRequestSchema) -> CrearTrabajoCommand:
    return CrearTrabajoCommand(
        descripcion=schema.descripcion,
        urgencia=schema.urgencia,
        pais=schema.ubicacion.pais,
        ciudad=schema.ubicacion.ciudad,
        direccion=schema.ubicacion.direccion,
        sub_trabajos=tuple(
            SubTrabajoSolicitado(
                clave=sub.clave,
                categoria=sub.categoria,
                descripcion=sub.descripcion,
                depende_de=tuple(sub.depende_de),
            )
            for sub in schema.sub_trabajos
        ),
        moneda=schema.moneda,
    )


def a_comando_asignar(
    trabajo_id: str, sub_trabajo_id: str, schema: AsignarProveedorRequestSchema
) -> AsignarProveedorCommand:
    return AsignarProveedorCommand(
        trabajo_id, sub_trabajo_id, str(schema.proveedor_id), schema.monto_cotizado
    )


def a_comando_iniciar(trabajo_id: str, sub_trabajo_id: str) -> IniciarSubTrabajoCommand:
    return IniciarSubTrabajoCommand(trabajo_id, sub_trabajo_id)


def a_comando_completar(
    trabajo_id: str, sub_trabajo_id: str, schema: CompletarSubTrabajoRequestSchema
) -> CompletarSubTrabajoCommand:
    return CompletarSubTrabajoCommand(trabajo_id, sub_trabajo_id, tuple(schema.evidencias))


def a_comando_rediagnostico(
    trabajo_id: str, schema: RegistrarRediagnosticoRequestSchema
) -> RegistrarRediagnosticoCommand:
    return RegistrarRediagnosticoCommand(
        trabajo_id=trabajo_id,
        hallazgo=schema.hallazgo,
        categoria=schema.categoria,
        descripcion=schema.descripcion,
        bloquea_a=tuple(schema.bloquea_a),
    )


def a_comando_cancelar(
    trabajo_id: str, schema: CancelarTrabajoRequestSchema
) -> CancelarTrabajoCommand:
    return CancelarTrabajoCommand(trabajo_id, schema.motivo)


def a_comando_cerrar(trabajo_id: str) -> CerrarTrabajoCommand:
    return CerrarTrabajoCommand(trabajo_id)


def a_query_trabajo(trabajo_id: str) -> ObtenerTrabajoQuery:
    return ObtenerTrabajoQuery(trabajo_id)


def a_query_listar(
    estado: str | None, partner_id: str | None, limite: int
) -> ListarTrabajosQuery:
    return ListarTrabajosQuery(estado=estado, partner_id=partner_id, limite=limite)


def a_schema_trabajo(dto: TrabajoDTO) -> TrabajoResponseSchema:
    return TrabajoResponseSchema(
        id=dto.id,
        canal=dto.canal,
        partner_id=dto.partner_id,
        referencia_externa=dto.referencia_externa,
        descripcion=dto.descripcion,
        urgencia=dto.urgencia,
        pais=dto.pais,
        ciudad=dto.ciudad,
        direccion=dto.direccion,
        moneda=dto.moneda,
        estado=dto.estado,
        costo_total=dto.costo_total,
        monto_maximo=dto.monto_maximo,
        sla_horas=dto.sla_horas,
        fecha_creacion=dto.fecha_creacion,
        sub_trabajos=[a_schema_sub_trabajo(sub) for sub in dto.sub_trabajos],
    )


def a_schema_sub_trabajo(dto: SubTrabajoDTO) -> SubTrabajoResponseSchema:
    return SubTrabajoResponseSchema(
        id=dto.id,
        categoria=dto.categoria,
        descripcion=dto.descripcion,
        estado=dto.estado,
        depende_de=list(dto.depende_de),
        proveedor_id=dto.proveedor_id,
        monto_cotizado=dto.monto_cotizado,
        evidencias=list(dto.evidencias),
    )
