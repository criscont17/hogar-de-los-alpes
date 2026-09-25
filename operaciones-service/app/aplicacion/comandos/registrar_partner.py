from dataclasses import dataclass
from decimal import Decimal

from app.aplicacion.dtos import RegistroDePartnerDTO
from app.aplicacion.eventos import despachar_eventos_pendientes
from app.aplicacion.mapeo import partner_a_dto
from app.aplicacion.puertos import (
    CatalogoDeAdaptadores,
    DomainEventDispatcher,
    UnidadDeTrabajo,
)
from app.dominio.partner import (
    AcuerdoComercial,
    CondicionComercial,
    Partner,
    PartnerId,
    TipoCondicion,
)


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

    No requiere codigo: las reglas comerciales son datos del agregado `Partner`.
    """

    def __init__(
        self,
        uow: UnidadDeTrabajo,
        adaptadores: CatalogoDeAdaptadores,
        dispatcher: DomainEventDispatcher,
    ) -> None:
        self._uow = uow
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
        with self._uow as uow:
            # Leer el acuerdo vigente y escribir el nuevo ocurre en una sola transaccion:
            # dos renegociaciones simultaneas no pueden mezclarse.
            partner = uow.partners.obtener_por_id(partner_id)
            creado = partner is None
            if partner is None:
                partner = Partner.registrar(partner_id, comando.nombre, comando.pais, acuerdo)
            else:
                partner.actualizar(comando.nombre, comando.pais, acuerdo)
            uow.partners.guardar(partner)
            uow.confirmar()
        despachar_eventos_pendientes(partner, self._dispatcher)
        return RegistroDePartnerDTO(
            partner=partner_a_dto(partner, self._adaptadores.tiene(str(partner.id))),
            creado=creado,
        )
