"""Puerta de entrada de los partners B2B2C y administración de sus acuerdos.

Las solicitudes de trabajo se reciben crudas (JSON propio, SOAP, webhook, texto) porque
su forma la define cada partner. La ruta no las interpreta: el caso de uso genérico las
traduce con el adaptador del partner y la respuesta vuelve en su mismo formato.
"""

from fastapi import APIRouter, Depends, Request, Response, status

from app.aplicacion.comandos import CrearTrabajoDesdePartnerHandler, RegistrarPartnerHandler
from app.aplicacion.errores import SolicitudDePartnerInvalidaError
from app.aplicacion.queries import (
    ConsultarTrabajoDePartnerHandler,
    ListarPartnersHandler,
    ObtenerPartnerHandler,
)
from app.infraestructura.adaptadores.acl_partners import CatalogoDeAdaptadoresEnMemoria

from .dependencias import (
    obtener_catalogo,
    obtener_consultar_handler,
    obtener_crear_desde_partner_handler,
    obtener_listar_handler,
    obtener_partner_handler,
    obtener_registrar_handler,
)
from .mappers import (
    a_comando_desde_partner,
    a_comando_registrar,
    a_query_listar,
    a_query_partner,
    a_query_trabajo,
    a_schema_partner,
    a_schema_salud,
)
from .schemas import (
    PartnerResponseSchema,
    RegistrarPartnerRequestSchema,
    SaludPartnerResponseSchema,
    SimularPartnerRequestSchema,
)

router = APIRouter(prefix="/partners", tags=["Partners B2B2C"])

CUERPO_EN_FORMATO_DEL_PARTNER = {
    "requestBody": {
        "required": True,
        "description": "Solicitud en el formato propio del partner (ver README).",
        "content": {
            "application/json": {"schema": {"type": "object"}},
            "text/xml": {"schema": {"type": "string"}},
            "text/plain": {"schema": {"type": "string"}},
        },
    }
}


async def leer_contenido(request: Request) -> str:
    cuerpo = await request.body()
    try:
        return cuerpo.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SolicitudDePartnerInvalidaError("El cuerpo debe estar codificado en UTF-8") from exc


@router.get("", response_model=list[PartnerResponseSchema])
def listar_partners(
    handler: ListarPartnersHandler = Depends(obtener_listar_handler),
) -> list[PartnerResponseSchema]:
    return [a_schema_partner(dto) for dto in handler.ejecutar(a_query_listar())]


@router.get("/{partner_id}", response_model=PartnerResponseSchema)
def obtener_partner(
    partner_id: str,
    handler: ObtenerPartnerHandler = Depends(obtener_partner_handler),
) -> PartnerResponseSchema:
    return a_schema_partner(handler.ejecutar(a_query_partner(partner_id)))


@router.put(
    "/{partner_id}",
    response_model=PartnerResponseSchema,
    responses={201: {"description": "Partner registrado"}, 200: {"description": "Acuerdo renegociado"}},
)
def registrar_partner(
    partner_id: str,
    schema: RegistrarPartnerRequestSchema,
    response: Response,
    handler: RegistrarPartnerHandler = Depends(obtener_registrar_handler),
) -> PartnerResponseSchema:
    """Onboarding contractual: registra el partner con su acuerdo, o lo renegocia."""

    resultado = handler.ejecutar(a_comando_registrar(partner_id, schema))
    response.status_code = status.HTTP_201_CREATED if resultado.creado else status.HTTP_200_OK
    return a_schema_partner(resultado.partner)


@router.post(
    "/{partner_id}/trabajos",
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra=CUERPO_EN_FORMATO_DEL_PARTNER,
    responses={200: {"description": "La referencia ya existía: se devuelve su estado"}},
)
def crear_trabajo_desde_partner(
    partner_id: str,
    contenido: str = Depends(leer_contenido),
    handler: CrearTrabajoDesdePartnerHandler = Depends(obtener_crear_desde_partner_handler),
) -> Response:
    """Recibe la solicitud y la entrega a GestionDeTrabajosBC; el trabajo se crea de forma asíncrona."""

    resultado = handler.ejecutar(a_comando_desde_partner(partner_id, contenido))
    return Response(
        content=resultado.respuesta.contenido,
        media_type=resultado.respuesta.media_type,
        status_code=status.HTTP_202_ACCEPTED if resultado.nueva else status.HTTP_200_OK,
    )


@router.get("/{partner_id}/trabajos/{referencia_externa}")
def consultar_trabajo_de_partner(
    partner_id: str,
    referencia_externa: str,
    handler: ConsultarTrabajoDePartnerHandler = Depends(obtener_consultar_handler),
) -> Response:
    respuesta = handler.ejecutar(a_query_trabajo(partner_id, referencia_externa))
    return Response(content=respuesta.contenido, media_type=respuesta.media_type)


@router.get("/{partner_id}/salud", response_model=SaludPartnerResponseSchema)
def salud_de_partner(
    partner_id: str,
    catalogo: CatalogoDeAdaptadoresEnMemoria = Depends(obtener_catalogo),
) -> SaludPartnerResponseSchema:
    return a_schema_salud(
        catalogo.sincronizador(partner_id).salud(), catalogo.cliente(partner_id).disponible
    )


@router.put("/{partner_id}/simulacion", response_model=SaludPartnerResponseSchema)
def simular_disponibilidad_de_partner(
    partner_id: str,
    schema: SimularPartnerRequestSchema,
    catalogo: CatalogoDeAdaptadoresEnMemoria = Depends(obtener_catalogo),
) -> SaludPartnerResponseSchema:
    """Simula la caída o recuperación del core del partner para observar el circuit breaker."""

    cliente = catalogo.cliente(partner_id)
    cliente.disponible = schema.disponible
    return a_schema_salud(catalogo.sincronizador(partner_id).salud(), cliente.disponible)
