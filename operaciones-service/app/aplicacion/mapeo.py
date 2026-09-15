from app.aplicacion.dtos import CondicionComercialDTO, PartnerDTO
from app.dominio.partner import Partner


def partner_a_dto(partner: Partner, tiene_adaptador: bool) -> PartnerDTO:
    acuerdo = partner.acuerdo
    return PartnerDTO(
        partner_id=str(partner.id),
        nombre=partner.nombre,
        pais=partner.pais,
        red_de_proveedores=(
            tuple(sorted(acuerdo.red_de_proveedores))
            if acuerdo.red_de_proveedores is not None
            else None
        ),
        condiciones=tuple(
            CondicionComercialDTO(tipo=c.tipo.value, clave=c.clave, valor=c.valor)
            for c in acuerdo.condiciones
        ),
        tiene_adaptador=tiene_adaptador,
        fecha_registro=partner.fecha_registro,
    )
