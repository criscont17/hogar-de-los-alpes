from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import RegistroDePartnerDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import partner_a_dto
from app.aplicacion.puertos import CatalogoDeAdaptadores, DomainEventDispatcher
from app.dominio.partner import (
    AcuerdoComercial,
    CondicionComercial,
    Partner,
    PartnerId,
    TipoCondicion,
)
from app.dominio.partner.partner_repository import PartnerRepository


@dataclass(frozen=True)
class CondicionComercialSolicitada:
    tipo: str
    clave: str
    valor: Decimal


@dataclass(frozen=True)
class RegistrarPartnerCommand:
    partner_id: str
    nombre: str
    pais: str
    condiciones: tuple[CondicionComercialSolicitada, ...]
    red_de_proveedores: tuple[str, ...] | None = None


class RegistrarPartnerHandler:
    """Onboarding contractual: registra un partner con su acuerdo o renegocia el vigente.

    No requiere código: las reglas comerciales son datos del agregado `Partner`.
    """

    def __init__(
        self,
        repo: PartnerRepository,
        adaptadores: CatalogoDeAdaptadores,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._repo = repo
        self._adaptadores = adaptadores
        self._dispatcher = dispatcher

    def ejecutar(self, comando: RegistrarPartnerCommand) -> RegistroDePartnerDTO:
        acuerdo = AcuerdoComercial(
            condiciones=tuple(
                CondicionComercial(TipoCondicion(c.tipo.strip().upper()), c.clave, c.valor)
                for c in comando.condiciones
            ),
            red_de_proveedores=(
                frozenset(comando.red_de_proveedores)
                if comando.red_de_proveedores is not None
                else None
            ),
        )
        partner_id = PartnerId(comando.partner_id)
        partner = self._repo.obtener_por_id(partner_id)
        creado = partner is None
        if partner is None:
            partner = Partner.registrar(partner_id, comando.nombre, comando.pais, acuerdo)
        else:
            partner.actualizar(comando.nombre, comando.pais, acuerdo)
        self._repo.guardar(partner)
        despachar_eventos_pendientes(partner, self._dispatcher)
        return RegistroDePartnerDTO(
            partner=partner_a_dto(partner, self._adaptadores.tiene(str(partner.id))),
            creado=creado,
        )
