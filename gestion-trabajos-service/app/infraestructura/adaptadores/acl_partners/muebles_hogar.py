"""Adaptador de Muebles del Hogar: comercio que vende cocinas y closets e incluye
la instalación. Integra por webhooks JSON en inglés.

Particularidades que solo conoce este archivo:
- Cada ítem vendido trae los servicios que necesita. Dentro de un ítem se
  respetan fases: desconexiones (plomería, electricidad), luego enchape, luego
  carpintería y al final retoques de pintura. Ítems distintos son independientes.
- Tarifa pactada por orden: tope fijo según el país.
- `priority` (standard | express) define el SLA; usa la red abierta de HdA.
- Recibe webhooks `installation.*`, incluido el avance de cada paso.

Ejemplo de solicitud:

    {
      "event": "installation.requested",
      "order_id": "MH-55012",
      "priority": "express",
      "customer_address": {"country": "CO", "city": "Medellin", "line1": "Calle 10 # 43-20"},
      "items": [
        {"sku": "COC-INT-01", "name": "Cocina integral",
         "services": ["plumbing_disconnect", "carpentry_install", "paint_touchup"]}
      ]
    }
"""

import json
from collections import defaultdict
from decimal import Decimal
from typing import Any

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
    SubTrabajoCompletadoV1,
    TrabajoCanceladoV1,
    TrabajoCerradoV1,
    TrabajoRediagnosticadoV1,
)
from app.dominio.trabajo import Categoria, EstadoSubTrabajo, EstadoTrabajo, Urgencia
from app.seedwork.aplicacion import IntegrationEvent

from .base import AdaptadorDePartnerBase, campo, leer_json, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "application/json"
EVENTO_DE_SOLICITUD = "installation.requested"

# servicio del comercio: (categoría en HdA, fase dentro del ítem)
SERVICIOS = {
    "plumbing_disconnect": (Categoria.PLOMERIA, 1),
    "electrical_disconnect": (Categoria.ELECTRICIDAD, 1),
    "tiling": (Categoria.BALDOSERIA, 2),
    "carpentry_install": (Categoria.CARPINTERIA, 3),
    "paint_touchup": (Categoria.PINTURA, 4),
}

URGENCIA_Y_SLA_POR_PRIORIDAD = {
    "standard": (Urgencia.MEDIA, 72),
    "express": (Urgencia.ALTA, 24),
}

MONEDA_Y_TOPE_POR_PAIS = {
    "CO": ("COP", Decimal("3000000")),
    "MX": ("MXN", Decimal("15000")),
}

STATUS_DEL_TRABAJO = {
    EstadoTrabajo.CREADO.value: "scheduled",
    EstadoTrabajo.EN_EJECUCION.value: "in_progress",
    EstadoTrabajo.CERRADO.value: "completed",
    EstadoTrabajo.CANCELADO.value: "cancelled",
}

STATUS_DEL_PASO = {
    EstadoSubTrabajo.BLOQUEADO.value: "waiting",
    EstadoSubTrabajo.PENDIENTE.value: "pending",
    EstadoSubTrabajo.ASIGNADO.value: "assigned",
    EstadoSubTrabajo.EN_EJECUCION.value: "in_progress",
    EstadoSubTrabajo.COMPLETADO.value: "done",
    EstadoSubTrabajo.CANCELADO.value: "cancelled",
}


class MueblesHogarAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "muebles-hogar"

    def traducir_solicitud(self, contenido: str) -> SolicitudDeTrabajo:
        datos = leer_json(contenido)
        evento = campo(datos, "event")
        if evento != EVENTO_DE_SOLICITUD:
            raise SolicitudDePartnerInvalidaError(f"Webhook no soportado: {evento}")
        direccion = campo(datos, "customer_address", dict)
        pais = campo(direccion, "country").upper()
        moneda, tope = traducir_valor(MONEDA_Y_TOPE_POR_PAIS, pais, "País")
        urgencia, sla_horas = traducir_valor(
            URGENCIA_Y_SLA_POR_PRIORIDAD, campo(datos, "priority").lower(), "Prioridad"
        )
        items = campo(datos, "items", list)
        if not items:
            raise SolicitudDePartnerInvalidaError("La orden no trae ítems para instalar")

        sub_trabajos: list[SubTrabajoSolicitado] = []
        nombres: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                raise SolicitudDePartnerInvalidaError("Cada ítem debe ser un objeto")
            nombres.append(campo(item, "name"))
            sub_trabajos.extend(self._instalacion(item))

        return SolicitudDeTrabajo(
            referencia_externa=campo(datos, "order_id"),
            descripcion="Instalación de " + ", ".join(nombres),
            urgencia=urgencia.value,
            pais=pais,
            ciudad=campo(direccion, "city"),
            direccion=campo(direccion, "line1"),
            moneda=moneda,
            sub_trabajos=tuple(sub_trabajos),
            condiciones=CondicionesDelAcuerdo(monto_maximo=tope, sla_horas=sla_horas),
        )

    def traducir_estado(self, trabajo: TrabajoDTO) -> RespuestaDePartner:
        cuerpo = {
            "order_id": trabajo.referencia_externa,
            "hda_job_id": trabajo.id,
            "status": STATUS_DEL_TRABAJO[trabajo.estado],
            "steps": [
                {
                    "step_id": sub.id,
                    "trade": sub.categoria,
                    "description": sub.descripcion,
                    "status": STATUS_DEL_PASO[sub.estado],
                }
                for sub in trabajo.sub_trabajos
            ],
        }
        return RespuestaDePartner(json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    def traducir_evento(self, evento: IntegrationEvent) -> MensajeParaPartner | None:
        if not isinstance(evento, EventoDeIntegracionDeTrabajo):
            return None
        datos: dict[str, Any]
        if isinstance(evento, SubTrabajoCompletadoV1):
            nombre = "installation.step_completed"
            datos = {"step_id": evento.sub_trabajo_id, "evidence": list(evento.evidencias)}
        elif isinstance(evento, TrabajoRediagnosticadoV1):
            nombre = "installation.rescheduled"
            datos = {"reason": evento.hallazgo, "new_step_id": evento.sub_trabajo_agregado_id}
        elif isinstance(evento, TrabajoCanceladoV1):
            nombre = "installation.cancelled"
            datos = {"reason": evento.motivo}
        elif isinstance(evento, TrabajoCerradoV1):
            nombre = "installation.completed"
            datos = {"total": evento.costo_total, "currency": evento.moneda}
        else:
            return None
        cuerpo = {
            "event": nombre,
            "order_id": evento.referencia_externa,
            "occurred_at": evento.occurred_at.isoformat(),
            "hda_event_id": str(evento.event_id),
            "data": datos,
        }
        return MensajeParaPartner(nombre, json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    @staticmethod
    def _instalacion(item: dict[str, Any]) -> list[SubTrabajoSolicitado]:
        sku = campo(item, "sku")
        nombre = campo(item, "name")
        servicios = campo(item, "services", list)
        if not servicios:
            raise SolicitudDePartnerInvalidaError(f"El ítem {sku} no trae servicios")

        por_fase: dict[int, list[tuple[str, Categoria]]] = defaultdict(list)
        for servicio in servicios:
            if not isinstance(servicio, str):
                raise SolicitudDePartnerInvalidaError(f"Servicio inválido en el ítem {sku}")
            categoria, fase = traducir_valor(SERVICIOS, servicio, "Servicio")
            por_fase[fase].append((servicio, categoria))

        sub_trabajos: list[SubTrabajoSolicitado] = []
        fase_anterior: tuple[str, ...] = ()
        for fase in sorted(por_fase):
            claves: list[str] = []
            for servicio, categoria in por_fase[fase]:
                clave = f"{sku}:{servicio}"
                sub_trabajos.append(
                    SubTrabajoSolicitado(
                        clave=clave,
                        categoria=categoria.value,
                        descripcion=f"{nombre}: {servicio.replace('_', ' ')}",
                        depende_de=fase_anterior,
                    )
                )
                claves.append(clave)
            fase_anterior = tuple(claves)
        return sub_trabajos
