from fastapi import APIRouter, Depends, Query, status

from app.aplicacion.comandos import (
    AsignarProveedorHandler,
    CancelarTrabajoHandler,
    CerrarTrabajoHandler,
    CompletarSubTrabajoHandler,
    CrearTrabajoHandler,
    IniciarSubTrabajoHandler,
    RegistrarRediagnosticoHandler,
)
from app.aplicacion.queries import ListarTrabajosHandler, ObtenerTrabajoHandler

from .dependencias import (
    obtener_asignar_handler,
    obtener_cancelar_handler,
    obtener_cerrar_handler,
    obtener_completar_handler,
    obtener_crear_handler,
    obtener_iniciar_handler,
    obtener_listar_handler,
    obtener_rediagnostico_handler,
    obtener_trabajo_handler,
)
from .mappers import (
    a_comando_asignar,
    a_comando_cancelar,
    a_comando_cerrar,
    a_comando_completar,
    a_comando_crear,
    a_comando_iniciar,
    a_comando_rediagnostico,
    a_query_listar,
    a_query_trabajo,
    a_schema_trabajo,
)
from .schemas import (
    AsignarProveedorRequestSchema,
    CancelarTrabajoRequestSchema,
    CompletarSubTrabajoRequestSchema,
    CrearTrabajoRequestSchema,
    RegistrarRediagnosticoRequestSchema,
    TrabajoResponseSchema,
)

router = APIRouter(prefix="/trabajos", tags=["Trabajos"])


@router.post("", response_model=TrabajoResponseSchema, status_code=status.HTTP_201_CREATED)
def crear_trabajo(
    schema: CrearTrabajoRequestSchema,
    handler: CrearTrabajoHandler = Depends(obtener_crear_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_comando_crear(schema)))


@router.get("", response_model=list[TrabajoResponseSchema])
def listar_trabajos(
    estado: str | None = Query(default=None),
    partner_id: str | None = Query(default=None),
    limite: int = Query(default=50, ge=1, le=200),
    handler: ListarTrabajosHandler = Depends(obtener_listar_handler),
) -> list[TrabajoResponseSchema]:
    dtos = handler.ejecutar(a_query_listar(estado, partner_id, limite))
    return [a_schema_trabajo(dto) for dto in dtos]


@router.get("/{trabajo_id}", response_model=TrabajoResponseSchema)
def obtener_trabajo(
    trabajo_id: str,
    handler: ObtenerTrabajoHandler = Depends(obtener_trabajo_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_query_trabajo(trabajo_id)))


@router.post(
    "/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/asignar",
    response_model=TrabajoResponseSchema,
)
def asignar_proveedor(
    trabajo_id: str,
    sub_trabajo_id: str,
    schema: AsignarProveedorRequestSchema,
    handler: AsignarProveedorHandler = Depends(obtener_asignar_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(
        handler.ejecutar(a_comando_asignar(trabajo_id, sub_trabajo_id, schema))
    )


@router.post(
    "/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/iniciar",
    response_model=TrabajoResponseSchema,
)
def iniciar_sub_trabajo(
    trabajo_id: str,
    sub_trabajo_id: str,
    handler: IniciarSubTrabajoHandler = Depends(obtener_iniciar_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_comando_iniciar(trabajo_id, sub_trabajo_id)))


@router.post(
    "/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/completar",
    response_model=TrabajoResponseSchema,
)
def completar_sub_trabajo(
    trabajo_id: str,
    sub_trabajo_id: str,
    schema: CompletarSubTrabajoRequestSchema,
    handler: CompletarSubTrabajoHandler = Depends(obtener_completar_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(
        handler.ejecutar(a_comando_completar(trabajo_id, sub_trabajo_id, schema))
    )


@router.post("/{trabajo_id}/rediagnosticar", response_model=TrabajoResponseSchema)
def registrar_rediagnostico(
    trabajo_id: str,
    schema: RegistrarRediagnosticoRequestSchema,
    handler: RegistrarRediagnosticoHandler = Depends(obtener_rediagnostico_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_comando_rediagnostico(trabajo_id, schema)))


@router.post("/{trabajo_id}/cancelar", response_model=TrabajoResponseSchema)
def cancelar_trabajo(
    trabajo_id: str,
    schema: CancelarTrabajoRequestSchema,
    handler: CancelarTrabajoHandler = Depends(obtener_cancelar_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_comando_cancelar(trabajo_id, schema)))


@router.post("/{trabajo_id}/cerrar", response_model=TrabajoResponseSchema)
def cerrar_trabajo(
    trabajo_id: str,
    handler: CerrarTrabajoHandler = Depends(obtener_cerrar_handler),
) -> TrabajoResponseSchema:
    return a_schema_trabajo(handler.ejecutar(a_comando_cerrar(trabajo_id)))


# Alias REST de las dos operaciones anteriores, para exponer el CRUD completo sobre el
# recurso `trabajo`. No agregan lógica: reusan el mismo comando, así que el agregado sigue
# validando la transición.


@router.patch(
    "/{trabajo_id}/sub-trabajos/{sub_trabajo_id}",
    response_model=TrabajoResponseSchema,
)
def actualizar_sub_trabajo(
    trabajo_id: str,
    sub_trabajo_id: str,
    schema: AsignarProveedorRequestSchema,
    handler: AsignarProveedorHandler = Depends(obtener_asignar_handler),
) -> TrabajoResponseSchema:
    """Asigna o reasigna el proveedor y la cotización de un sub-trabajo."""

    return a_schema_trabajo(
        handler.ejecutar(a_comando_asignar(trabajo_id, sub_trabajo_id, schema))
    )


@router.delete("/{trabajo_id}", response_model=TrabajoResponseSchema)
def eliminar_trabajo(
    trabajo_id: str,
    motivo: str = Query(
        default="Eliminado por solicitud del cliente",
        min_length=1,
        description="Motivo que queda registrado en el evento TrabajoCancelado",
    ),
    handler: CancelarTrabajoHandler = Depends(obtener_cancelar_handler),
) -> TrabajoResponseSchema:
    """Borrado lógico: cancela el trabajo y liquida lo que alcanzó a completarse.

    Un trabajo nunca se borra físicamente, porque PagosBC y OperacionesBC ya consumieron
    sus eventos y deben poder compensar.
    """

    return a_schema_trabajo(
        handler.ejecutar(a_comando_cancelar(trabajo_id, CancelarTrabajoRequestSchema(motivo=motivo)))
    )
