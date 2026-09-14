"""Puerta de entrada de los partners B2B2C a la capa anti-corrupción.

El cuerpo se recibe crudo (JSON propio, SOAP, webhook) porque su forma la define
cada partner; la ruta no lo interpreta y lo entrega al caso de uso genérico, que
lo traduce a través del adaptador registrado. La respuesta vuelve en el mismo
formato del partner.
"""

from fastapi import APIRouter, Depends, Request, Response, status

from app.aplicacion.comandos import CrearTrabajoDesdePartnerHandler
from app.aplicacion.errores import SolicitudDePartnerInvalidaError
from app.aplicacion.queries import ConsultarTrabajoDePartnerHandler
from app.infraestructura.adaptadores.acl_partners import CatalogoDePartnersEnMemoria

from .dependencias import (
    obtener_catalogo,
    obtener_consultar_de_partner_handler,
    obtener_crear_desde_partner_handler,
)
from .mappers import a_comando_desde_partner, a_query_de_partner, a_schema_salud
from .schemas import SaludPartnerResponseSchema, SimularPartnerRequestSchema

router = APIRouter(prefix="/partners", tags=["Partners B2B2C (ACL)"])

CUERPO_EN_FORMATO_DEL_PARTNER = {
    "requestBody": {
        "required": True,
        "description": "Solicitud en el formato propio del partner (ver README).",
        "content": {
            "application/json": {"schema": {"type": "object"}},
            "text/xml": {"schema": {"type": "string"}},
        },
    }
}


async def leer_contenido(request: Request) -> str:
    cuerpo = await request.body()
    try:
        return cuerpo.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SolicitudDePartnerInvalidaError("El cuerpo debe estar codificado en UTF-8") from exc


@router.get("", response_model=list[SaludPartnerResponseSchema])
def listar_partners(
    catalogo: CatalogoDePartnersEnMemoria = Depends(obtener_catalogo),
) -> list[SaludPartnerResponseSchema]:
    return [
        a_schema_salud(catalogo.sincronizador(pid).salud(), catalogo.cliente(pid).disponible)
        for pid in catalogo.partner_ids()
    ]


@router.post(
    "/{partner_id}/trabajos",
    status_code=status.HTTP_201_CREATED,
    openapi_extra=CUERPO_EN_FORMATO_DEL_PARTNER,
    responses={200: {"description": "La referencia ya existía: se devuelve el trabajo original"}},
)
def crear_trabajo_desde_partner(
    partner_id: str,
    contenido: str = Depends(leer_contenido),
    handler: CrearTrabajoDesdePartnerHandler = Depends(obtener_crear_desde_partner_handler),
) -> Response:
    resultado = handler.ejecutar(a_comando_desde_partner(partner_id, contenido))
    return Response(
        content=resultado.respuesta.contenido,
        media_type=resultado.respuesta.media_type,
        status_code=status.HTTP_201_CREATED if resultado.creado else status.HTTP_200_OK,
        headers={"Location": f"/trabajos/{resultado.trabajo_id}"},
    )


@router.get("/{partner_id}/trabajos/{referencia_externa}")
def consultar_trabajo_de_partner(
    partner_id: str,
    referencia_externa: str,
    handler: ConsultarTrabajoDePartnerHandler = Depends(obtener_consultar_de_partner_handler),
) -> Response:
    respuesta = handler.ejecutar(a_query_de_partner(partner_id, referencia_externa))
    return Response(content=respuesta.contenido, media_type=respuesta.media_type)


@router.get("/{partner_id}/salud", response_model=SaludPartnerResponseSchema)
def salud_de_partner(
    partner_id: str,
    catalogo: CatalogoDePartnersEnMemoria = Depends(obtener_catalogo),
) -> SaludPartnerResponseSchema:
    return a_schema_salud(
        catalogo.sincronizador(partner_id).salud(), catalogo.cliente(partner_id).disponible
    )


@router.put("/{partner_id}/simulacion", response_model=SaludPartnerResponseSchema)
def simular_disponibilidad_de_partner(
    partner_id: str,
    schema: SimularPartnerRequestSchema,
    catalogo: CatalogoDePartnersEnMemoria = Depends(obtener_catalogo),
) -> SaludPartnerResponseSchema:
    """Simula la caída o recuperación del core del partner para observar el circuit breaker."""

    cliente = catalogo.cliente(partner_id)
    cliente.disponible = schema.disponible
    return a_schema_salud(catalogo.sincronizador(partner_id).salud(), cliente.disponible)
