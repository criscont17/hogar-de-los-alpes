from app.aplicacion.comandos import (
    CondicionComercialSolicitada,
    CrearTrabajoDesdePartnerCommand,
    RegistrarPartnerCommand,
)
from app.aplicacion.dtos import PartnerDTO
from app.aplicacion.queries import (
    ConsultarTrabajoDePartnerQuery,
    ListarPartnersQuery,
    ObtenerPartnerQuery,
)
from app.infraestructura.adaptadores.acl_partners import SaludDePartner

from .schemas import (
    CondicionComercialSchema,
    PartnerResponseSchema,
    RegistrarPartnerRequestSchema,
    SaludPartnerResponseSchema,
)


def a_comando_registrar(
    partner_id: str, schema: RegistrarPartnerRequestSchema
) -> RegistrarPartnerCommand:
    return RegistrarPartnerCommand(
        partner_id=partner_id,
        nombre=schema.nombre,
        pais=schema.pais,
        condiciones=tuple(
            CondicionComercialSolicitada(tipo=c.tipo, clave=c.clave, valor=c.valor)
            for c in schema.condiciones
        ),
        red_de_proveedores=(
            tuple(schema.red_de_proveedores) if schema.red_de_proveedores is not None else None
        ),
    )


def a_comando_desde_partner(partner_id: str, contenido: str) -> CrearTrabajoDesdePartnerCommand:
    return CrearTrabajoDesdePartnerCommand(partner_id=partner_id, contenido=contenido)


def a_query_listar() -> ListarPartnersQuery:
    return ListarPartnersQuery()


def a_query_partner(partner_id: str) -> ObtenerPartnerQuery:
    return ObtenerPartnerQuery(partner_id)


def a_query_trabajo(partner_id: str, referencia_externa: str) -> ConsultarTrabajoDePartnerQuery:
    return ConsultarTrabajoDePartnerQuery(partner_id, referencia_externa)


def a_schema_partner(dto: PartnerDTO) -> PartnerResponseSchema:
    return PartnerResponseSchema(
        partner_id=dto.partner_id,
        nombre=dto.nombre,
        pais=dto.pais,
        red_de_proveedores=list(dto.red_de_proveedores) if dto.red_de_proveedores is not None else None,
        condiciones=[
            CondicionComercialSchema(tipo=c.tipo, clave=c.clave, valor=c.valor)
            for c in dto.condiciones
        ],
        tiene_adaptador=dto.tiene_adaptador,
        fecha_registro=dto.fecha_registro,
    )


def a_schema_salud(salud: SaludDePartner, core_disponible: bool) -> SaludPartnerResponseSchema:
    return SaludPartnerResponseSchema(
        partner_id=salud.partner_id,
        circuito=salud.circuito,
        fallos_consecutivos=salud.fallos_consecutivos,
        pendientes=salud.pendientes,
        sincronizados=salud.sincronizados,
        degradaciones=salud.degradaciones,
        descartados=salud.descartados,
        ultimo_error=salud.ultimo_error,
        core_disponible=core_disponible,
    )
