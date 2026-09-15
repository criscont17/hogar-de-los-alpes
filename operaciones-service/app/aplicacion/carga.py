from app.dominio.errores import PartnerNoRegistradoError
from app.dominio.partner import Partner, PartnerId
from app.dominio.partner.partner_repository import PartnerRepository


def cargar_partner(repo: PartnerRepository, partner_id: str) -> Partner:
    partner = repo.obtener_por_id(PartnerId(partner_id))
    if partner is None:
        raise PartnerNoRegistradoError(
            f"El partner '{partner_id}' no está registrado en OperacionesBC"
        )
    return partner
