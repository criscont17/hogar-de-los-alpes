from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.dominio.errores import (
    DatosDelTrabajoInvalidosError,
    MontoInvalidoError,
    MontoMaximoExcedidoError,
    ProveedorNoPermitidoError,
    SubTrabajoNoEncontradoError,
    TrabajoFinalizadoError,
    TrabajoIncompletoError,
)
from app.seedwork.dominio import AggregateRoot

from .acuerdo_comercial import AcuerdoComercial
from .dinero import Dinero
from .enums import Categoria, EstadoSubTrabajo, EstadoTrabajo, Urgencia
from .eventos import (
    AsignacionRechazada,
    Liquidacion,
    ProveedorAsignado,
    SubTrabajoCompletado,
    SubTrabajoDesbloqueado,
    SubTrabajoIniciado,
    TrabajoCancelado,
    TrabajoCerrado,
    TrabajoRediagnosticado,
)
from .identificadores import SubTrabajoId, TrabajoId
from .origen import OrigenDelTrabajo
from .sub_trabajo import SubTrabajo
from .ubicacion import Ubicacion


class Trabajo(AggregateRoot[TrabajoId]):
    """Raíz del ciclo de vida de un trabajo, sea cual sea su canal de origen.

    Es la única puerta para cambiar sus sub-trabajos: así garantiza que un bloqueo
    solo se levanta cuando terminan todas sus dependencias y que ninguna asignación
    rompe el acuerdo comercial con el que se creó el trabajo.
    """

    def __init__(
        self,
        id: TrabajoId,
        origen: OrigenDelTrabajo,
        descripcion: str,
        urgencia: Urgencia,
        ubicacion: Ubicacion,
        moneda: str,
        acuerdo: AcuerdoComercial,
        sub_trabajos: Iterable[SubTrabajo],
        estado: EstadoTrabajo,
        fecha_creacion: datetime,
    ) -> None:
        super().__init__()
        descripcion = (descripcion or "").strip()
        if not descripcion:
            raise DatosDelTrabajoInvalidosError("La descripción del trabajo es obligatoria")
        self.id = id
        self.origen = origen
        self.descripcion = descripcion
        self.urgencia = urgencia
        self.ubicacion = ubicacion
        self._sin_costo = Dinero(Decimal("0"), moneda)
        if acuerdo.monto_maximo is not None:
            acuerdo.monto_maximo.validar_misma_moneda(self._sin_costo)
        self.acuerdo = acuerdo
        self._sub_trabajos = list(sub_trabajos)
        if not self._sub_trabajos:
            raise DatosDelTrabajoInvalidosError("Un trabajo requiere al menos un sub-trabajo")
        self._estado = estado
        self.fecha_creacion = fecha_creacion

    @property
    def estado(self) -> EstadoTrabajo:
        return self._estado

    @property
    def moneda(self) -> str:
        return self._sin_costo.moneda

    @property
    def sub_trabajos(self) -> tuple[SubTrabajo, ...]:
        return tuple(self._sub_trabajos)

    @property
    def costo_total(self) -> Dinero:
        return self._costo_excluyendo(None)

    def sub_trabajo(self, sub_trabajo_id: SubTrabajoId) -> SubTrabajo:
        for sub_trabajo in self._sub_trabajos:
            if sub_trabajo.id == sub_trabajo_id:
                return sub_trabajo
        raise SubTrabajoNoEncontradoError("El sub-trabajo no pertenece al trabajo")

    def asignar_proveedor(
        self, sub_trabajo_id: SubTrabajoId, proveedor_id: str, monto_cotizado: Dinero
    ) -> None:
        self._exigir_activo()
        sub_trabajo = self.sub_trabajo(sub_trabajo_id)
        sub_trabajo.exigir_asignable()
        proveedor_id = (proveedor_id or "").strip()
        if not proveedor_id:
            raise DatosDelTrabajoInvalidosError("proveedor_id es obligatorio")
        if monto_cotizado.monto <= 0:
            raise MontoInvalidoError("La cotización debe ser mayor que cero")
        monto_cotizado.validar_misma_moneda(self._sin_costo)

        if not self.acuerdo.admite_proveedor(proveedor_id):
            motivo = "El proveedor no pertenece a la red permitida por el acuerdo"
            self._rechazar_asignacion(sub_trabajo, proveedor_id, monto_cotizado, motivo)
            raise ProveedorNoPermitidoError(motivo)
        costo_proyectado = self._costo_excluyendo(sub_trabajo).sumar(monto_cotizado)
        if not self.acuerdo.admite_costo(costo_proyectado):
            motivo = (
                f"El costo proyectado {costo_proyectado.monto} {self.moneda} supera el "
                f"monto máximo del acuerdo ({self.acuerdo.monto_maximo.monto} {self.moneda})"
            )
            self._rechazar_asignacion(sub_trabajo, proveedor_id, monto_cotizado, motivo)
            raise MontoMaximoExcedidoError(motivo)

        reasignacion = sub_trabajo.proveedor_id is not None
        sub_trabajo.asignar(proveedor_id, monto_cotizado)
        self.add_domain_event(
            ProveedorAsignado(
                **self._origen_del_evento(),
                sub_trabajo_id=str(sub_trabajo.id),
                proveedor_id=proveedor_id,
                monto_cotizado=monto_cotizado.monto,
                moneda=self.moneda,
                reasignacion=reasignacion,
            )
        )

    def iniciar_sub_trabajo(self, sub_trabajo_id: SubTrabajoId) -> None:
        self._exigir_activo()
        sub_trabajo = self.sub_trabajo(sub_trabajo_id)
        sub_trabajo.iniciar()
        if self._estado is EstadoTrabajo.CREADO:
            self._estado = EstadoTrabajo.EN_EJECUCION
        self.add_domain_event(
            SubTrabajoIniciado(
                **self._origen_del_evento(),
                sub_trabajo_id=str(sub_trabajo.id),
                proveedor_id=str(sub_trabajo.proveedor_id),
            )
        )

    def completar_sub_trabajo(
        self, sub_trabajo_id: SubTrabajoId, evidencias: Iterable[str]
    ) -> None:
        self._exigir_activo()
        sub_trabajo = self.sub_trabajo(sub_trabajo_id)
        sub_trabajo.completar(evidencias)
        self.add_domain_event(
            SubTrabajoCompletado(
                **self._origen_del_evento(),
                sub_trabajo_id=str(sub_trabajo.id),
                proveedor_id=str(sub_trabajo.proveedor_id),
                evidencias=sub_trabajo.evidencias,
            )
        )
        self._desbloquear_dependientes()

    def registrar_rediagnostico(
        self,
        hallazgo: str,
        categoria: Categoria,
        descripcion: str,
        bloquea_a: Iterable[SubTrabajoId],
    ) -> SubTrabajoId:
        """Agrega el sub-trabajo que exige un hallazgo y congela lo que depende de él."""

        self._exigir_activo()
        hallazgo = (hallazgo or "").strip()
        if not hallazgo:
            raise DatosDelTrabajoInvalidosError("El re-diagnóstico requiere describir el hallazgo")
        congelados = [self.sub_trabajo(sub_id) for sub_id in dict.fromkeys(bloquea_a)]
        # Se valida todo antes de mutar: si uno ya inició, el re-diagnóstico se
        # rechaza completo y el agregado queda intacto.
        for sub_trabajo in congelados:
            sub_trabajo.exigir_congelable()
        nuevo = SubTrabajo(
            SubTrabajoId.nuevo(), categoria, descripcion, (), EstadoSubTrabajo.PENDIENTE
        )

        self._sub_trabajos.append(nuevo)
        for sub_trabajo in congelados:
            sub_trabajo.congelar_hasta(nuevo.id)
        self.add_domain_event(
            TrabajoRediagnosticado(
                **self._origen_del_evento(),
                hallazgo=hallazgo,
                sub_trabajo_agregado_id=str(nuevo.id),
                categoria=categoria.value,
                sub_trabajos_congelados=tuple(str(sub.id) for sub in congelados),
            )
        )
        return nuevo.id

    def cancelar(self, motivo: str) -> None:
        self._exigir_activo()
        motivo = (motivo or "").strip()
        if not motivo:
            raise DatosDelTrabajoInvalidosError("El motivo de cancelación es obligatorio")
        liquidaciones = self._liquidaciones()
        cancelados: list[str] = []
        for sub_trabajo in self._sub_trabajos:
            if sub_trabajo.estado is not EstadoSubTrabajo.COMPLETADO:
                sub_trabajo.cancelar()
                cancelados.append(str(sub_trabajo.id))
        self._estado = EstadoTrabajo.CANCELADO
        self.add_domain_event(
            TrabajoCancelado(
                **self._origen_del_evento(),
                motivo=motivo,
                sub_trabajos_cancelados=tuple(cancelados),
                liquidaciones=liquidaciones,
                moneda=self.moneda,
            )
        )

    def cerrar(self) -> None:
        self._exigir_activo()
        faltantes = sum(
            1 for sub in self._sub_trabajos if sub.estado is not EstadoSubTrabajo.COMPLETADO
        )
        if faltantes:
            raise TrabajoIncompletoError(
                f"No se puede cerrar: faltan {faltantes} sub-trabajos por completar"
            )
        self._estado = EstadoTrabajo.CERRADO
        self.add_domain_event(
            TrabajoCerrado(
                **self._origen_del_evento(),
                costo_total=self.costo_total.monto,
                moneda=self.moneda,
                liquidaciones=self._liquidaciones(),
            )
        )

    def _desbloquear_dependientes(self) -> None:
        completados = {
            sub.id for sub in self._sub_trabajos if sub.estado is EstadoSubTrabajo.COMPLETADO
        }
        for sub_trabajo in self._sub_trabajos:
            if (
                sub_trabajo.estado is EstadoSubTrabajo.BLOQUEADO
                and sub_trabajo.depende_de <= completados
            ):
                sub_trabajo.desbloquear()
                self.add_domain_event(
                    SubTrabajoDesbloqueado(
                        **self._origen_del_evento(),
                        sub_trabajo_id=str(sub_trabajo.id),
                        categoria=sub_trabajo.categoria.value,
                        estado=sub_trabajo.estado.value,
                    )
                )

    def _rechazar_asignacion(
        self, sub_trabajo: SubTrabajo, proveedor_id: str, monto: Dinero, motivo: str
    ) -> None:
        self.add_domain_event(
            AsignacionRechazada(
                **self._origen_del_evento(),
                sub_trabajo_id=str(sub_trabajo.id),
                proveedor_id=proveedor_id,
                monto_cotizado=monto.monto,
                moneda=self.moneda,
                motivo_rechazo=motivo,
            )
        )

    def _exigir_activo(self) -> None:
        if self._estado in (EstadoTrabajo.CERRADO, EstadoTrabajo.CANCELADO):
            raise TrabajoFinalizadoError(
                f"El trabajo está {self._estado.value} y no admite cambios"
            )

    def _costo_excluyendo(self, excluido: SubTrabajo | None) -> Dinero:
        total = self._sin_costo
        for sub_trabajo in self._sub_trabajos:
            if (
                sub_trabajo is excluido
                or sub_trabajo.monto_cotizado is None
                or sub_trabajo.estado is EstadoSubTrabajo.CANCELADO
            ):
                continue
            total = total.sumar(sub_trabajo.monto_cotizado)
        return total

    def _liquidaciones(self) -> tuple[Liquidacion, ...]:
        return tuple(
            Liquidacion(
                sub_trabajo_id=str(sub.id),
                proveedor_id=sub.proveedor_id,
                monto=sub.monto_cotizado.monto,
            )
            for sub in self._sub_trabajos
            if sub.estado is EstadoSubTrabajo.COMPLETADO
            and sub.proveedor_id is not None
            and sub.monto_cotizado is not None
        )

    def _origen_del_evento(self) -> dict[str, Any]:
        return {
            "trabajo_id": str(self.id),
            "partner_id": self.origen.partner_id,
            "referencia_externa": self.origen.referencia_externa,
        }
