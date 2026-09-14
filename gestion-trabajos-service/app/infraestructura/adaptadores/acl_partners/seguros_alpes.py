"""Adaptador de Seguros de los Alpes: aseguradora con API REST propia en JSON.

Particularidades que solo conoce este archivo:
- Identifica el trabajo por `numeroSiniestro` y lo cubierto por `coberturas` con
  códigos propios (COB-PLOM, COB-PINT...). Una cobertura puede exigir que otra
  termine antes (`requiereTerminar`).
- El monto máximo depende del plan de la póliza y solo atienden proveedores de
  su red homologada.
- Su `prioridad` (CRITICA..BAJA) fija el SLA contractual.
- Recibe novedades como JSON con `tipoNovedad`.

Ejemplo de solicitud:

    {
      "numeroSiniestro": "SA-2026-000123",
      "poliza": {"numero": "H-88231", "plan": "PLUS"},
      "prioridad": "ALTA",
      "descripcionSiniestro": "Calentador estalló y humedeció el muro",
      "predio": {"pais": "CO", "ciudad": "Bogota", "direccion": "Cra 7 # 45-10"},
      "coberturas": [
        {"codigo": "COB-PLOM", "detalle": "Reparar tubería del calentador"},
        {"codigo": "COB-PINT", "detalle": "Resanar y pintar muro",
         "requiereTerminar": ["COB-PLOM"]}
      ]
    }
"""

import json
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
    ProveedorAsignadoV1,
    TrabajoCanceladoV1,
    TrabajoCerradoV1,
    TrabajoRediagnosticadoV1,
)
from app.dominio.trabajo import Categoria, EstadoTrabajo, Urgencia
from app.seedwork.aplicacion import IntegrationEvent

from .base import AdaptadorDePartnerBase, campo, leer_json, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "application/json"

CATEGORIA_POR_COBERTURA = {
    "COB-PLOM": Categoria.PLOMERIA,
    "COB-ELEC": Categoria.ELECTRICIDAD,
    "COB-CARP": Categoria.CARPINTERIA,
    "COB-PINT": Categoria.PINTURA,
    "COB-BALD": Categoria.BALDOSERIA,
}
COBERTURA_POR_CATEGORIA = {
    categoria.value: codigo for codigo, categoria in CATEGORIA_POR_COBERTURA.items()
}

URGENCIA_Y_SLA_POR_PRIORIDAD = {
    "CRITICA": (Urgencia.EMERGENCIA, 4),
    "ALTA": (Urgencia.ALTA, 24),
    "MEDIA": (Urgencia.MEDIA, 72),
    "BAJA": (Urgencia.BAJA, 120),
}

TOPE_POR_PLAN = {
    "BASICO": Decimal("1500000"),
    "PLUS": Decimal("4000000"),
    "PREMIUM": Decimal("10000000"),
}

# Proveedores homologados por la aseguradora. En producción vendría de su core o
# de ProveedoresBC; se fija aquí porque es regla del partner, no de HdA.
RED_HOMOLOGADA = frozenset(
    {
        "5f0c3a52-8d1e-4d7b-9a10-3c1a7e2b9d01",
        "8a4e6b13-2f7c-4c9e-b5d2-7e9f1a3c6b02",
    }
)

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajo.CREADO.value: "RECIBIDO",
    EstadoTrabajo.EN_EJECUCION.value: "EN_ATENCION",
    EstadoTrabajo.CERRADO.value: "FINALIZADO",
    EstadoTrabajo.CANCELADO.value: "ANULADO",
}


class SegurosAlpesAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "seguros-alpes"

    def traducir_solicitud(self, contenido: str) -> SolicitudDeTrabajo:
        datos = leer_json(contenido)
        poliza = campo(datos, "poliza", dict)
        predio = campo(datos, "predio", dict)
        coberturas = campo(datos, "coberturas", list)
        if not coberturas:
            raise SolicitudDePartnerInvalidaError("El siniestro no trae coberturas")
        urgencia, sla_horas = traducir_valor(
            URGENCIA_Y_SLA_POR_PRIORIDAD, campo(datos, "prioridad").upper(), "Prioridad"
        )
        return SolicitudDeTrabajo(
            referencia_externa=campo(datos, "numeroSiniestro"),
            descripcion=campo(datos, "descripcionSiniestro"),
            urgencia=urgencia.value,
            pais=campo(predio, "pais"),
            ciudad=campo(predio, "ciudad"),
            direccion=campo(predio, "direccion"),
            moneda="COP",
            sub_trabajos=tuple(self._sub_trabajo(cobertura) for cobertura in coberturas),
            condiciones=CondicionesDelAcuerdo(
                monto_maximo=traducir_valor(
                    TOPE_POR_PLAN, campo(poliza, "plan").upper(), "Plan de póliza"
                ),
                proveedores_permitidos=RED_HOMOLOGADA,
                sla_horas=sla_horas,
            ),
        )

    def traducir_estado(self, trabajo: TrabajoDTO) -> RespuestaDePartner:
        cuerpo = {
            "numeroSiniestro": trabajo.referencia_externa,
            "idTrabajoHdA": trabajo.id,
            "estado": ESTADO_PARA_EL_PARTNER[trabajo.estado],
            "coberturas": [
                {
                    "codigo": COBERTURA_POR_CATEGORIA.get(sub.categoria, "SIN-COBERTURA"),
                    "detalle": sub.descripcion,
                    "estado": sub.estado,
                    "proveedor": sub.proveedor_id,
                }
                for sub in trabajo.sub_trabajos
            ],
            "costoAcumulado": str(trabajo.costo_total),
            "topePoliza": str(trabajo.monto_maximo) if trabajo.monto_maximo is not None else None,
            "moneda": trabajo.moneda,
        }
        return RespuestaDePartner(json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    def traducir_evento(self, evento: IntegrationEvent) -> MensajeParaPartner | None:
        if not isinstance(evento, EventoDeIntegracionDeTrabajo):
            return None
        detalle: dict[str, Any]
        if isinstance(evento, ProveedorAsignadoV1):
            tipo = "PROVEEDOR_ASIGNADO"
            detalle = {"proveedor": evento.proveedor_id, "valorCotizado": evento.monto_cotizado}
        elif isinstance(evento, TrabajoRediagnosticadoV1):
            tipo = "CAMBIO_DE_ALCANCE"
            detalle = {
                "hallazgo": evento.hallazgo,
                "coberturaAdicional": COBERTURA_POR_CATEGORIA.get(evento.categoria, "SIN-COBERTURA"),
            }
        elif isinstance(evento, TrabajoCanceladoV1):
            tipo = "ANULACION"
            detalle = {"motivo": evento.motivo}
        elif isinstance(evento, TrabajoCerradoV1):
            tipo = "CIERRE"
            detalle = {"valorTotal": evento.costo_total, "moneda": evento.moneda}
        else:
            return None
        cuerpo = {
            "numeroSiniestro": evento.referencia_externa,
            "tipoNovedad": tipo,
            "fechaNovedad": evento.occurred_at.isoformat(),
            "idEventoHdA": str(evento.event_id),
            **detalle,
        }
        return MensajeParaPartner(tipo, json.dumps(cuerpo, ensure_ascii=False), MEDIA_TYPE)

    @staticmethod
    def _sub_trabajo(cobertura: object) -> SubTrabajoSolicitado:
        if not isinstance(cobertura, dict):
            raise SolicitudDePartnerInvalidaError("Cada cobertura debe ser un objeto")
        codigo = campo(cobertura, "codigo").upper()
        requiere = cobertura.get("requiereTerminar", [])
        if not isinstance(requiere, list) or not all(isinstance(c, str) for c in requiere):
            raise SolicitudDePartnerInvalidaError("'requiereTerminar' debe ser una lista de códigos")
        return SubTrabajoSolicitado(
            clave=codigo,
            categoria=traducir_valor(CATEGORIA_POR_COBERTURA, codigo, "Cobertura").value,
            descripcion=campo(cobertura, "detalle"),
            depende_de=tuple(c.upper() for c in requiere),
        )
