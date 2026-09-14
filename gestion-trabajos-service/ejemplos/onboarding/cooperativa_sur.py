"""Adaptador de Cooperativa Sur: partner listo para demostrar el onboarding.

NO está registrado. Para integrarlo (escenario de Modificabilidad #3):

1. Copie este archivo a
   `app/infraestructura/adaptadores/acl_partners/cooperativa_sur.py`.
2. En `app/infraestructura/adaptadores/acl_partners/registro.py` agregue
       from .cooperativa_sur import CooperativaSurAdapter
   y `CooperativaSurAdapter` al final de la tupla `ADAPTADORES_REGISTRADOS`.
3. Reinicie el servicio.

Después, `git diff --stat -- app/dominio app/aplicacion` debe quedar vacío.

Particularidades que solo conoce este archivo:
- Cooperativa de vivienda argentina que envía cada orden como una línea de texto
  plano: `referencia|ciudad|dirección|urgencia|pasos`.
- En `pasos`, `>` separa etapas en secuencia y `+` agrupa oficios que van en
  paralelo dentro de la misma etapa.
- Opera en pesos argentinos con un tope fijo por orden y trabaja con la red
  abierta de proveedores de HdA.
- Responde y recibe novedades también en texto plano.

Ejemplo de solicitud:

    CS-2026-0042|Buenos Aires|Av. Corrientes 1234|URGENTE|PLOM>ELEC+PINT
"""

from decimal import Decimal

from app.aplicacion.dtos import (
    CondicionesDelAcuerdo,
    RespuestaDePartner,
    SolicitudDeTrabajo,
    SubTrabajoSolicitado,
    TrabajoDTO,
)
from app.aplicacion.errores import SolicitudDePartnerInvalidaError
from app.aplicacion.eventos_integracion import (
    EventoDeIntegracionDeTrabajo,
    TrabajoCanceladoV1,
    TrabajoCerradoV1,
    TrabajoRediagnosticadoV1,
)
from app.dominio.trabajo import Categoria, EstadoSubTrabajo, EstadoTrabajo, Urgencia
from app.seedwork.aplicacion import IntegrationEvent

from .base import AdaptadorDePartnerBase, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "text/plain"
TOPE_POR_ORDEN = Decimal("800000")

CATEGORIA_POR_OFICIO = {
    "PLOM": Categoria.PLOMERIA,
    "ELEC": Categoria.ELECTRICIDAD,
    "CARP": Categoria.CARPINTERIA,
    "PINT": Categoria.PINTURA,
    "BALD": Categoria.BALDOSERIA,
}

URGENCIA_Y_SLA = {
    "URGENTE": (Urgencia.ALTA, 24),
    "NORMAL": (Urgencia.MEDIA, 72),
}

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajo.CREADO.value: "RECIBIDA",
    EstadoTrabajo.EN_EJECUCION.value: "EN_OBRA",
    EstadoTrabajo.CERRADO.value: "TERMINADA",
    EstadoTrabajo.CANCELADO.value: "ANULADA",
}


class CooperativaSurAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "cooperativa-sur"

    def traducir_solicitud(self, contenido: str) -> SolicitudDeTrabajo:
        campos = [campo.strip() for campo in contenido.strip().split("|")]
        if len(campos) != 5 or not all(campos):
            raise SolicitudDePartnerInvalidaError(
                "Se esperaba 'referencia|ciudad|dirección|urgencia|pasos'"
            )
        referencia, ciudad, direccion, urgencia_partner, pasos = campos
        urgencia, sla_horas = traducir_valor(URGENCIA_Y_SLA, urgencia_partner.upper(), "Urgencia")

        sub_trabajos: list[SubTrabajoSolicitado] = []
        etapa_anterior: tuple[str, ...] = ()
        for numero, etapa in enumerate(pasos.split(">"), start=1):
            claves: list[str] = []
            for oficio in etapa.split("+"):
                oficio = oficio.strip().upper()
                categoria = traducir_valor(CATEGORIA_POR_OFICIO, oficio, "Oficio")
                clave = f"{numero}-{oficio}"
                sub_trabajos.append(
                    SubTrabajoSolicitado(
                        clave=clave,
                        categoria=categoria.value,
                        descripcion=f"{categoria.value} en {direccion}",
                        depende_de=etapa_anterior,
                    )
                )
                claves.append(clave)
            etapa_anterior = tuple(claves)

        return SolicitudDeTrabajo(
            referencia_externa=referencia,
            descripcion=f"Orden de la cooperativa {referencia}",
            urgencia=urgencia.value,
            pais="AR",
            ciudad=ciudad,
            direccion=direccion,
            moneda="ARS",
            sub_trabajos=tuple(sub_trabajos),
            condiciones=CondicionesDelAcuerdo(monto_maximo=TOPE_POR_ORDEN, sla_horas=sla_horas),
        )

    def traducir_estado(self, trabajo: TrabajoDTO) -> RespuestaDePartner:
        terminados = sum(
            1 for sub in trabajo.sub_trabajos if sub.estado == EstadoSubTrabajo.COMPLETADO.value
        )
        contenido = "|".join(
            [
                trabajo.referencia_externa or "",
                ESTADO_PARA_EL_PARTNER[trabajo.estado],
                f"{terminados}/{len(trabajo.sub_trabajos)}",
                f"{trabajo.costo_total} {trabajo.moneda}",
            ]
        )
        return RespuestaDePartner(contenido, MEDIA_TYPE)

    def traducir_evento(self, evento: IntegrationEvent) -> MensajeParaPartner | None:
        if not isinstance(evento, EventoDeIntegracionDeTrabajo):
            return None
        if isinstance(evento, TrabajoCerradoV1):
            tipo, detalle = "TERMINADA", f"{evento.costo_total} {evento.moneda}"
        elif isinstance(evento, TrabajoCanceladoV1):
            tipo, detalle = "ANULADA", evento.motivo
        elif isinstance(evento, TrabajoRediagnosticadoV1):
            tipo, detalle = "NOVEDAD", evento.hallazgo
        else:
            return None
        return MensajeParaPartner(
            tipo, f"{evento.referencia_externa}|{tipo}|{detalle}", MEDIA_TYPE
        )
