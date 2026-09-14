from collections.abc import Sequence
from datetime import datetime, timezone

from .acuerdo_comercial import AcuerdoComercial
from .enums import EstadoSubTrabajo, EstadoTrabajo, Urgencia
from .eventos import DetalleSubTrabajo, TrabajoCreado
from .flujo import ordenar_flujo
from .identificadores import SubTrabajoId, TrabajoId
from .origen import OrigenDelTrabajo
from .plan import SubTrabajoPlaneado
from .sub_trabajo import SubTrabajo
from .trabajo import Trabajo
from .ubicacion import Ubicacion


class TrabajoFactory:
    @staticmethod
    def crear(
        origen: OrigenDelTrabajo,
        descripcion: str,
        urgencia: Urgencia,
        ubicacion: Ubicacion,
        moneda: str,
        acuerdo: AcuerdoComercial,
        plan: Sequence[SubTrabajoPlaneado],
    ) -> Trabajo:
        """Construye el flujo del trabajo: lo que no depende de nada queda listo para
        ejecutarse en paralelo; lo demás nace bloqueado."""

        ordenados = ordenar_flujo(plan)
        ids = {planeado.clave: SubTrabajoId.nuevo() for planeado in ordenados}
        sub_trabajos = [
            SubTrabajo(
                id=ids[planeado.clave],
                categoria=planeado.categoria,
                descripcion=planeado.descripcion,
                depende_de=[ids[clave] for clave in planeado.depende_de],
                estado=(
                    EstadoSubTrabajo.BLOQUEADO if planeado.depende_de else EstadoSubTrabajo.PENDIENTE
                ),
            )
            for planeado in ordenados
        ]
        fecha = datetime.now(timezone.utc)
        trabajo = Trabajo(
            id=TrabajoId.nuevo(),
            origen=origen,
            descripcion=descripcion,
            urgencia=urgencia,
            ubicacion=ubicacion,
            moneda=moneda,
            acuerdo=acuerdo,
            sub_trabajos=sub_trabajos,
            estado=EstadoTrabajo.CREADO,
            fecha_creacion=fecha,
        )
        trabajo.add_domain_event(
            TrabajoCreado(
                occurred_at=fecha,
                trabajo_id=str(trabajo.id),
                partner_id=origen.partner_id,
                referencia_externa=origen.referencia_externa,
                canal=origen.canal.value,
                descripcion=trabajo.descripcion,
                urgencia=urgencia.value,
                pais=ubicacion.pais,
                ciudad=ubicacion.ciudad,
                moneda=trabajo.moneda,
                monto_maximo=acuerdo.monto_maximo.monto if acuerdo.monto_maximo else None,
                sla_horas=acuerdo.sla_horas,
                sub_trabajos=tuple(
                    DetalleSubTrabajo(
                        sub_trabajo_id=str(sub.id),
                        categoria=sub.categoria.value,
                        estado=sub.estado.value,
                        depende_de=tuple(sorted(str(dep) for dep in sub.depende_de)),
                    )
                    for sub in trabajo.sub_trabajos
                ),
            )
        )
        return trabajo
