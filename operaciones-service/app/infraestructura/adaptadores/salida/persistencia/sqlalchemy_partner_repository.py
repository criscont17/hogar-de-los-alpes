from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dominio.partner import (
    AcuerdoComercial,
    CondicionComercial,
    Partner,
    PartnerId,
    TipoCondicion,
)
from app.dominio.partner.partner_repository import PartnerRepository

from .modelos_orm import PartnerModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyPartnerRepository(PartnerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def guardar(self, partner: Partner) -> None:
        try:
            model = self._session.get(PartnerModel, str(partner.id))
            if model is None:
                model = PartnerModel(id=str(partner.id), fecha_registro=partner.fecha_registro)
                self._session.add(model)
            acuerdo = partner.acuerdo
            model.nombre = partner.nombre
            model.pais = partner.pais
            model.red_de_proveedores = (
                sorted(acuerdo.red_de_proveedores) if acuerdo.red_de_proveedores is not None else None
            )
            model.condiciones = [
                {"tipo": c.tipo.value, "clave": c.clave, "valor": str(c.valor)}
                for c in acuerdo.condiciones
            ]
            model.fecha_actualizacion = datetime.now(timezone.utc)
            self._session.commit()
        except Exception:
            self._session.rollback()
            raise

    def obtener_por_id(self, id: PartnerId) -> Partner | None:
        return self._a_dominio(self._session.get(PartnerModel, str(id)))

    def listar(self) -> list[Partner]:
        modelos = self._session.scalars(select(PartnerModel).order_by(PartnerModel.id))
        return [self._a_dominio(model) for model in modelos]

    @staticmethod
    def _a_dominio(model: PartnerModel | None) -> Partner | None:
        if model is None:
            return None
        return Partner(
            id=PartnerId(model.id),
            nombre=model.nombre,
            pais=model.pais,
            acuerdo=AcuerdoComercial(
                condiciones=tuple(
                    CondicionComercial(TipoCondicion(c["tipo"]), c["clave"], Decimal(c["valor"]))
                    for c in model.condiciones
                ),
                red_de_proveedores=(
                    frozenset(model.red_de_proveedores)
                    if model.red_de_proveedores is not None
                    else None
                ),
            ),
            fecha_registro=_con_zona_horaria(model.fecha_registro),
        )
