from datetime import datetime, timezone
from decimal import Decimal

from app.dominio.errores import DatosDePartnerInvalidosError
from app.seedwork.dominio import AggregateRoot

from .acuerdo_comercial import AcuerdoComercial
from .condiciones_aplicables import CondicionesAplicables
from .eventos import AcuerdoRenegociado, PartnerRegistrado
from .identificadores import PartnerId


class Partner(AggregateRoot[PartnerId]):
    """Aliado B2B2C (aseguradora, banco o comercio) con un acuerdo comercial vigente.

    Es el dueño de las reglas del partner. Renegociar su acuerdo no altera los trabajos ya
    solicitados: GestionDeTrabajosBC guardó las condiciones vigentes cuando los creó.
    """

    def __init__(
        self,
        id: PartnerId,
        nombre: str,
        pais: str,
        acuerdo: AcuerdoComercial,
        fecha_registro: datetime,
    ) -> None:
        super().__init__()
        self.id = id
        self.nombre, self.pais = self._validar(nombre, pais)
        self._acuerdo = acuerdo
        self.fecha_registro = fecha_registro

    @classmethod
    def registrar(
        cls, id: PartnerId, nombre: str, pais: str, acuerdo: AcuerdoComercial
    ) -> "Partner":
        partner = cls(id, nombre, pais, acuerdo, datetime.now(timezone.utc))
        partner.add_domain_event(
            PartnerRegistrado(partner_id=str(id), nombre=partner.nombre, pais=partner.pais)
        )
        return partner

    @property
    def acuerdo(self) -> AcuerdoComercial:
        return self._acuerdo

    def actualizar(self, nombre: str, pais: str, acuerdo: AcuerdoComercial) -> None:
        self.nombre, self.pais = self._validar(nombre, pais)
        if acuerdo != self._acuerdo:
            self._acuerdo = acuerdo
            self.add_domain_event(AcuerdoRenegociado(partner_id=str(self.id)))

    def resolver_condiciones(
        self,
        clave_sla: str,
        clave_tope: str | None = None,
        tope_solicitado: Decimal | None = None,
    ) -> CondicionesAplicables:
        return self._acuerdo.resolver(clave_sla, clave_tope, tope_solicitado)

    @staticmethod
    def _validar(nombre: str, pais: str) -> tuple[str, str]:
        nombre = (nombre or "").strip()
        if not nombre:
            raise DatosDePartnerInvalidosError("El nombre del partner es obligatorio")
        pais = (pais or "").strip().upper()
        if len(pais) != 2 or not pais.isalpha():
            raise DatosDePartnerInvalidosError("El país del partner debe ser un código ISO alfa-2")
        return nombre, pais
