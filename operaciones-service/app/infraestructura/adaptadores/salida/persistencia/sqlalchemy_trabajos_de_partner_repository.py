from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.aplicacion.dtos import (
    EstadoTrabajoDePartner,
    SubTrabajoDePartnerDTO,
    TrabajoDePartnerDTO,
)
from app.aplicacion.errores import SolicitudYaRegistradaError
from app.aplicacion.puertos import TrabajosDePartnerRepository

from .modelos_orm import TrabajoDePartnerModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyTrabajosDePartnerRepository(TrabajosDePartnerRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def obtener(self, partner_id: str, referencia_externa: str) -> TrabajoDePartnerDTO | None:
        model = self._session.get(
            TrabajoDePartnerModel, (partner_id, referencia_externa), populate_existing=True
        )
        return self._a_dto(model) if model is not None else None

    def registrar_solicitud(self, trabajo: TrabajoDePartnerDTO) -> TrabajoDePartnerDTO:
        """Deja constancia de la solicitud si el partner no la habia pedido ya."""

        llave = (trabajo.partner_id, trabajo.referencia_externa)
        model = self._session.get(TrabajoDePartnerModel, llave, populate_existing=True)
        if model is not None and model.estado != EstadoTrabajoDePartner.RECHAZADO.value:
            return self._a_dto(model)
        if model is None:
            model = TrabajoDePartnerModel(
                partner_id=trabajo.partner_id, referencia_externa=trabajo.referencia_externa
            )
            self._session.add(model)
        self._copiar(trabajo, model)
        try:
            self._session.flush()
        except IntegrityError as exc:
            # El consumidor de eventos creo la vista entre la lectura y la escritura.
            raise SolicitudYaRegistradaError(
                "La vista del trabajo fue registrada por otro proceso"
            ) from exc
        return self._a_dto(model)

    def guardar(self, trabajo: TrabajoDePartnerDTO) -> None:
        """Actualiza la vista dentro de la transaccion abierta por la unidad de trabajo."""

        model = self._session.get(
            TrabajoDePartnerModel, (trabajo.partner_id, trabajo.referencia_externa)
        )
        if model is None:
            model = TrabajoDePartnerModel(
                partner_id=trabajo.partner_id, referencia_externa=trabajo.referencia_externa
            )
            self._session.add(model)
        self._copiar(trabajo, model)
        self._session.flush()

    @staticmethod
    def _copiar(trabajo: TrabajoDePartnerDTO, model: TrabajoDePartnerModel) -> None:
        model.estado = trabajo.estado.value
        model.trabajo_id = trabajo.trabajo_id
        model.moneda = trabajo.moneda
        model.monto_maximo = trabajo.monto_maximo
        model.sla_horas = trabajo.sla_horas
        model.costo_total = trabajo.costo_total
        model.motivo_rechazo = trabajo.motivo_rechazo
        model.sub_trabajos = [
            {
                "id": sub.id,
                "categoria": sub.categoria,
                "estado": sub.estado,
                "proveedor_id": sub.proveedor_id,
                "monto_cotizado": str(sub.monto_cotizado) if sub.monto_cotizado is not None else None,
            }
            for sub in trabajo.sub_trabajos
        ]
        model.fecha_solicitud = trabajo.fecha_solicitud
        model.fecha_actualizacion = datetime.now(timezone.utc)

    @staticmethod
    def _a_dto(model: TrabajoDePartnerModel) -> TrabajoDePartnerDTO:
        return TrabajoDePartnerDTO(
            partner_id=model.partner_id,
            referencia_externa=model.referencia_externa,
            estado=EstadoTrabajoDePartner(model.estado),
            fecha_solicitud=_con_zona_horaria(model.fecha_solicitud),
            trabajo_id=model.trabajo_id,
            moneda=model.moneda,
            monto_maximo=model.monto_maximo,
            sla_horas=model.sla_horas,
            costo_total=model.costo_total,
            motivo_rechazo=model.motivo_rechazo,
            sub_trabajos=tuple(
                SubTrabajoDePartnerDTO(
                    id=sub["id"],
                    categoria=sub["categoria"],
                    estado=sub["estado"],
                    proveedor_id=sub.get("proveedor_id"),
                    monto_cotizado=(
                        Decimal(sub["monto_cotizado"]) if sub.get("monto_cotizado") is not None else None
                    ),
                )
                for sub in model.sub_trabajos
            ),
        )
