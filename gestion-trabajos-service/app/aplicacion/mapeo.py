from collections.abc import Iterable

from app.aplicacion.dtos import (
    CondicionesDelAcuerdo,
    SubTrabajoDTO,
    SubTrabajoSolicitado,
    TrabajoDTO,
)
from app.dominio.trabajo import (
    Categoria,
    CondicionesDelTrabajo,
    Dinero,
    SubTrabajo,
    SubTrabajoPlaneado,
    Trabajo,
)


def trabajo_a_dto(trabajo: Trabajo) -> TrabajoDTO:
    return TrabajoDTO(
        id=str(trabajo.id),
        canal=trabajo.origen.canal.value,
        partner_id=trabajo.origen.partner_id,
        referencia_externa=trabajo.origen.referencia_externa,
        descripcion=trabajo.descripcion,
        urgencia=trabajo.urgencia.value,
        pais=trabajo.ubicacion.pais,
        ciudad=trabajo.ubicacion.ciudad,
        direccion=trabajo.ubicacion.direccion,
        moneda=trabajo.moneda,
        estado=trabajo.estado.value,
        costo_total=trabajo.costo_total.monto,
        monto_maximo=(
            trabajo.condiciones.monto_maximo.monto if trabajo.condiciones.monto_maximo else None
        ),
        sla_horas=trabajo.condiciones.sla_horas,
        fecha_creacion=trabajo.fecha_creacion,
        sub_trabajos=tuple(sub_trabajo_a_dto(sub) for sub in trabajo.sub_trabajos),
    )


def sub_trabajo_a_dto(sub_trabajo: SubTrabajo) -> SubTrabajoDTO:
    return SubTrabajoDTO(
        id=str(sub_trabajo.id),
        categoria=sub_trabajo.categoria.value,
        descripcion=sub_trabajo.descripcion,
        estado=sub_trabajo.estado.value,
        depende_de=tuple(sorted(str(dep) for dep in sub_trabajo.depende_de)),
        proveedor_id=sub_trabajo.proveedor_id,
        monto_cotizado=sub_trabajo.monto_cotizado.monto if sub_trabajo.monto_cotizado else None,
        evidencias=sub_trabajo.evidencias,
    )


def plan_desde_solicitados(
    solicitados: Iterable[SubTrabajoSolicitado],
) -> list[SubTrabajoPlaneado]:
    return [
        SubTrabajoPlaneado(
            clave=solicitado.clave,
            categoria=Categoria(solicitado.categoria),
            descripcion=solicitado.descripcion,
            depende_de=tuple(solicitado.depende_de),
        )
        for solicitado in solicitados
    ]


def condiciones_desde_dto(
    condiciones: CondicionesDelAcuerdo, moneda: str
) -> CondicionesDelTrabajo:
    return CondicionesDelTrabajo(
        monto_maximo=(
            Dinero(condiciones.monto_maximo, moneda)
            if condiciones.monto_maximo is not None
            else None
        ),
        proveedores_permitidos=condiciones.proveedores_permitidos,
        sla_horas=condiciones.sla_horas,
    )
