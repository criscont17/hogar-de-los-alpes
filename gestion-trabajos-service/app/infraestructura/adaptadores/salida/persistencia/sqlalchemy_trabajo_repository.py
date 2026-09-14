from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.exc import StaleDataError

from app.aplicacion.errores import ConflictoDeConcurrenciaError
from app.dominio.errores import TrabajoDuplicadoError
from app.dominio.trabajo import (
    AcuerdoComercial,
    CanalDeOrigen,
    Categoria,
    Dinero,
    EstadoSubTrabajo,
    EstadoTrabajo,
    OrigenDelTrabajo,
    SubTrabajo,
    SubTrabajoId,
    Trabajo,
    TrabajoId,
    Ubicacion,
    Urgencia,
)
from app.dominio.trabajo.trabajo_repository import TrabajoRepository

from .modelos_orm import SubTrabajoModel, TrabajoModel


def _con_zona_horaria(fecha: datetime) -> datetime:
    return fecha if fecha.tzinfo is not None else fecha.replace(tzinfo=timezone.utc)


class SqlAlchemyTrabajoRepository(TrabajoRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def guardar(self, trabajo: Trabajo) -> None:
        try:
            model = self._session.get(TrabajoModel, trabajo.id.valor)
            if model is None:
                model = self._nuevo_modelo(trabajo)
                self._session.add(model)
            model.estado = trabajo.estado.value
            # Siempre cambia, así que toda escritura pasa por la verificación de
            # versión aunque solo se hayan modificado sub-trabajos.
            model.fecha_actualizacion = datetime.now(timezone.utc)

            existentes = {sub.id: sub for sub in model.sub_trabajos}
            for orden, sub_trabajo in enumerate(trabajo.sub_trabajos):
                sub_model = existentes.get(sub_trabajo.id.valor)
                if sub_model is None:
                    sub_model = SubTrabajoModel(
                        id=sub_trabajo.id.valor,
                        trabajo_id=trabajo.id.valor,
                        orden=orden,
                        categoria=sub_trabajo.categoria.value,
                        descripcion=sub_trabajo.descripcion,
                    )
                    model.sub_trabajos.append(sub_model)
                sub_model.estado = sub_trabajo.estado.value
                sub_model.depende_de = sorted(str(dep) for dep in sub_trabajo.depende_de)
                sub_model.proveedor_id = sub_trabajo.proveedor_id
                sub_model.monto_cotizado = (
                    sub_trabajo.monto_cotizado.monto if sub_trabajo.monto_cotizado else None
                )
                sub_model.evidencias = list(sub_trabajo.evidencias)
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise TrabajoDuplicadoError(
                "Ya existe un trabajo con esa referencia para el partner"
            ) from exc
        except StaleDataError as exc:
            self._session.rollback()
            raise ConflictoDeConcurrenciaError(
                "El trabajo fue modificado por otra operación; vuelva a intentarlo"
            ) from exc
        except Exception:
            self._session.rollback()
            raise

    def obtener_por_id(self, id: TrabajoId) -> Trabajo | None:
        statement = (
            select(TrabajoModel)
            .where(TrabajoModel.id == id.valor)
            .options(selectinload(TrabajoModel.sub_trabajos))
        )
        return self._a_dominio(self._session.scalar(statement))

    def obtener_por_referencia_de_partner(
        self, partner_id: str, referencia_externa: str
    ) -> Trabajo | None:
        statement = (
            select(TrabajoModel)
            .where(
                TrabajoModel.partner_id == partner_id,
                TrabajoModel.referencia_externa == referencia_externa,
            )
            .options(selectinload(TrabajoModel.sub_trabajos))
        )
        return self._a_dominio(self._session.scalar(statement))

    def listar(
        self,
        estado: EstadoTrabajo | None = None,
        partner_id: str | None = None,
        limite: int = 50,
    ) -> list[Trabajo]:
        statement = (
            select(TrabajoModel)
            .options(selectinload(TrabajoModel.sub_trabajos))
            .order_by(TrabajoModel.fecha_creacion.desc())
            .limit(limite)
        )
        if estado is not None:
            statement = statement.where(TrabajoModel.estado == estado.value)
        if partner_id is not None:
            statement = statement.where(TrabajoModel.partner_id == partner_id)
        return [self._a_dominio(model) for model in self._session.scalars(statement)]

    @staticmethod
    def _nuevo_modelo(trabajo: Trabajo) -> TrabajoModel:
        acuerdo = trabajo.acuerdo
        return TrabajoModel(
            id=trabajo.id.valor,
            canal=trabajo.origen.canal.value,
            partner_id=trabajo.origen.partner_id,
            referencia_externa=trabajo.origen.referencia_externa,
            descripcion=trabajo.descripcion,
            urgencia=trabajo.urgencia.value,
            pais=trabajo.ubicacion.pais,
            ciudad=trabajo.ubicacion.ciudad,
            direccion=trabajo.ubicacion.direccion,
            moneda=trabajo.moneda,
            monto_maximo=acuerdo.monto_maximo.monto if acuerdo.monto_maximo else None,
            proveedores_permitidos=(
                sorted(acuerdo.proveedores_permitidos)
                if acuerdo.proveedores_permitidos is not None
                else None
            ),
            sla_horas=acuerdo.sla_horas,
            fecha_creacion=trabajo.fecha_creacion,
            sub_trabajos=[],
        )

    @staticmethod
    def _a_dominio(model: TrabajoModel | None) -> Trabajo | None:
        if model is None:
            return None
        moneda = model.moneda
        sub_trabajos = [
            SubTrabajo(
                id=SubTrabajoId(sub.id),
                categoria=Categoria(sub.categoria),
                descripcion=sub.descripcion,
                depende_de=[SubTrabajoId(dep) for dep in sub.depende_de],
                estado=EstadoSubTrabajo(sub.estado),
                proveedor_id=sub.proveedor_id,
                monto_cotizado=(
                    Dinero(sub.monto_cotizado, moneda) if sub.monto_cotizado is not None else None
                ),
                evidencias=sub.evidencias,
            )
            for sub in model.sub_trabajos
        ]
        return Trabajo(
            id=TrabajoId(model.id),
            origen=OrigenDelTrabajo(
                CanalDeOrigen(model.canal), model.partner_id, model.referencia_externa
            ),
            descripcion=model.descripcion,
            urgencia=Urgencia(model.urgencia),
            ubicacion=Ubicacion(model.pais, model.ciudad, model.direccion),
            moneda=moneda,
            acuerdo=AcuerdoComercial(
                monto_maximo=(
                    Dinero(model.monto_maximo, moneda) if model.monto_maximo is not None else None
                ),
                proveedores_permitidos=(
                    frozenset(model.proveedores_permitidos)
                    if model.proveedores_permitidos is not None
                    else None
                ),
                sla_horas=model.sla_horas,
            ),
            sub_trabajos=sub_trabajos,
            estado=EstadoTrabajo(model.estado),
            fecha_creacion=_con_zona_horaria(model.fecha_creacion),
        )
