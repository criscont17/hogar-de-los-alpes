"""Adaptador de Banco Andino: banco mexicano que integra por SOAP (XML).

Particularidades que solo conoce este archivo:
- La orden se identifica por `IdOrden` y trae su tope autorizado con moneda.
- Las actividades se agrupan por `etapa`: lo de una misma etapa va en paralelo y
  cada etapa espera a que termine completa la anterior.
- `NivelUrgencia` numérico (1 = crítica ... 4 = baja) define el SLA.
- Acepta cualquier proveedor acreditado por HdA: no impone red propia.
- Solo quiere enterarse de cierres, cancelaciones y cotizaciones rechazadas.

Ejemplo de solicitud:

    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                      xmlns:ba="urn:bancoandino:hogar:v3">
      <soapenv:Body>
        <ba:SolicitudOrdenServicio>
          <ba:IdOrden>BA-MX-7781</ba:IdOrden>
          <ba:NivelUrgencia>2</ba:NivelUrgencia>
          <ba:Resumen>Remodelación de cocina con fuga previa</ba:Resumen>
          <ba:Inmueble pais="MX" ciudad="Ciudad de Mexico">Av. Reforma 222</ba:Inmueble>
          <ba:TopeAutorizado moneda="MXN">25000.00</ba:TopeAutorizado>
          <ba:Actividades>
            <ba:Actividad etapa="1" oficio="FONTANERIA">Reparar tubería</ba:Actividad>
            <ba:Actividad etapa="2" oficio="AZULEJO">Cambiar azulejo</ba:Actividad>
            <ba:Actividad etapa="2" oficio="ELECTRICIDAD">Reubicar contactos</ba:Actividad>
            <ba:Actividad etapa="3" oficio="CARPINTERIA">Instalar gabinetes</ba:Actividad>
          </ba:Actividades>
        </ba:SolicitudOrdenServicio>
      </soapenv:Body>
    </soapenv:Envelope>
"""

import xml.etree.ElementTree as ET
from collections import defaultdict

from app.aplicacion.dtos import (
    CondicionesDelAcuerdo,
    RespuestaDePartner,
    SolicitudDeTrabajo,
    SubTrabajoSolicitado,
    TrabajoDTO,
)
from app.aplicacion.errores import SolicitudDePartnerInvalidaError
from app.aplicacion.eventos_integracion import (
    AsignacionRechazadaV1,
    EventoDeIntegracionDeTrabajo,
    TrabajoCanceladoV1,
    TrabajoCerradoV1,
)
from app.dominio.trabajo import Categoria, EstadoSubTrabajo, EstadoTrabajo, Urgencia
from app.seedwork.aplicacion import IntegrationEvent

from .base import AdaptadorDePartnerBase, decimal, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "text/xml"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_BANCO = "urn:bancoandino:hogar:v3"
NS = {"soapenv": NS_SOAP, "ba": NS_BANCO}

ET.register_namespace("soapenv", NS_SOAP)
ET.register_namespace("ba", NS_BANCO)

CATEGORIA_POR_OFICIO = {
    "FONTANERIA": Categoria.PLOMERIA,
    "ELECTRICIDAD": Categoria.ELECTRICIDAD,
    "CARPINTERIA": Categoria.CARPINTERIA,
    "PINTURA": Categoria.PINTURA,
    "AZULEJO": Categoria.BALDOSERIA,
}

URGENCIA_Y_SLA_POR_NIVEL = {
    "1": (Urgencia.EMERGENCIA, 6),
    "2": (Urgencia.ALTA, 24),
    "3": (Urgencia.MEDIA, 72),
    "4": (Urgencia.BAJA, 168),
}

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajo.CREADO.value: "REGISTRADA",
    EstadoTrabajo.EN_EJECUCION.value: "EN_PROCESO",
    EstadoTrabajo.CERRADO.value: "CONCLUIDA",
    EstadoTrabajo.CANCELADO.value: "CANCELADA",
}


class BancoAndinoAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "banco-andino"

    def traducir_solicitud(self, contenido: str) -> SolicitudDeTrabajo:
        if "<!DOCTYPE" in contenido.upper():
            # SOAP no admite DTD; rechazarla evita ataques de expansión de entidades.
            raise SolicitudDePartnerInvalidaError("La solicitud SOAP no puede declarar una DTD")
        try:
            raiz = ET.fromstring(contenido)
        except ET.ParseError as exc:
            raise SolicitudDePartnerInvalidaError(f"XML mal formado: {exc}") from exc
        orden = raiz.find("soapenv:Body/ba:SolicitudOrdenServicio", NS)
        if orden is None:
            raise SolicitudDePartnerInvalidaError(
                "El sobre SOAP no contiene SolicitudOrdenServicio"
            )
        inmueble = self._elemento(orden, "Inmueble")
        tope = self._elemento(orden, "TopeAutorizado")
        urgencia, sla_horas = traducir_valor(
            URGENCIA_Y_SLA_POR_NIVEL, self._texto(orden, "NivelUrgencia"), "Nivel de urgencia"
        )
        return SolicitudDeTrabajo(
            referencia_externa=self._texto(orden, "IdOrden"),
            descripcion=self._texto(orden, "Resumen"),
            urgencia=urgencia.value,
            pais=self._atributo(inmueble, "pais"),
            ciudad=self._atributo(inmueble, "ciudad"),
            direccion=self._texto_de(inmueble, "Inmueble"),
            moneda=self._atributo(tope, "moneda"),
            sub_trabajos=self._actividades(orden),
            condiciones=CondicionesDelAcuerdo(
                monto_maximo=decimal(tope.text, "TopeAutorizado"),
                sla_horas=sla_horas,
            ),
        )

    def traducir_estado(self, trabajo: TrabajoDTO) -> RespuestaDePartner:
        estado = ET.Element(f"{{{NS_BANCO}}}EstadoOrdenServicio")
        self._hijo(estado, "IdOrden", trabajo.referencia_externa or "")
        self._hijo(estado, "FolioHdA", trabajo.id)
        self._hijo(estado, "Estado", ESTADO_PARA_EL_PARTNER[trabajo.estado])
        terminadas = sum(
            1 for sub in trabajo.sub_trabajos if sub.estado == EstadoSubTrabajo.COMPLETADO.value
        )
        self._hijo(estado, "ActividadesTerminadas", str(terminadas))
        self._hijo(estado, "ActividadesTotales", str(len(trabajo.sub_trabajos)))
        self._hijo(estado, "MontoEjercido", str(trabajo.costo_total)).set("moneda", trabajo.moneda)
        return RespuestaDePartner(self._sobre(estado), MEDIA_TYPE)

    def traducir_evento(self, evento: IntegrationEvent) -> MensajeParaPartner | None:
        if not isinstance(evento, EventoDeIntegracionDeTrabajo):
            return None
        if isinstance(evento, TrabajoCerradoV1):
            operacion = "NotificarConclusionOrden"
        elif isinstance(evento, TrabajoCanceladoV1):
            operacion = "NotificarCancelacionOrden"
        elif isinstance(evento, AsignacionRechazadaV1):
            operacion = "NotificarCotizacionRechazada"
        else:
            return None

        notificacion = ET.Element(f"{{{NS_BANCO}}}{operacion}")
        self._hijo(notificacion, "IdOrden", evento.referencia_externa or "")
        self._hijo(notificacion, "Fecha", evento.occurred_at.isoformat())
        if isinstance(evento, TrabajoCerradoV1):
            self._hijo(notificacion, "MontoFinal", evento.costo_total).set("moneda", evento.moneda)
        elif isinstance(evento, TrabajoCanceladoV1):
            self._hijo(notificacion, "Motivo", evento.motivo)
        else:
            self._hijo(notificacion, "MontoCotizado", evento.monto_cotizado).set(
                "moneda", evento.moneda
            )
            self._hijo(notificacion, "Motivo", evento.motivo_rechazo)
        return MensajeParaPartner(operacion, self._sobre(notificacion), MEDIA_TYPE)

    def _actividades(self, orden: ET.Element) -> tuple[SubTrabajoSolicitado, ...]:
        actividades = orden.findall("ba:Actividades/ba:Actividad", NS)
        if not actividades:
            raise SolicitudDePartnerInvalidaError("La orden no trae actividades")
        por_etapa: dict[int, list[ET.Element]] = defaultdict(list)
        for actividad in actividades:
            etapa = self._atributo(actividad, "etapa")
            if not etapa.isdigit():
                raise SolicitudDePartnerInvalidaError(f"Etapa inválida: {etapa}")
            por_etapa[int(etapa)].append(actividad)

        sub_trabajos: list[SubTrabajoSolicitado] = []
        etapa_anterior: tuple[str, ...] = ()
        for etapa in sorted(por_etapa):
            claves: list[str] = []
            for indice, actividad in enumerate(por_etapa[etapa], start=1):
                clave = f"etapa-{etapa}-{indice}"
                oficio = self._atributo(actividad, "oficio").upper()
                sub_trabajos.append(
                    SubTrabajoSolicitado(
                        clave=clave,
                        categoria=traducir_valor(CATEGORIA_POR_OFICIO, oficio, "Oficio").value,
                        descripcion=self._texto_de(actividad, "Actividad"),
                        depende_de=etapa_anterior,
                    )
                )
                claves.append(clave)
            etapa_anterior = tuple(claves)
        return tuple(sub_trabajos)

    @staticmethod
    def _elemento(padre: ET.Element, nombre: str) -> ET.Element:
        elemento = padre.find(f"ba:{nombre}", NS)
        if elemento is None:
            raise SolicitudDePartnerInvalidaError(f"Falta el elemento obligatorio '{nombre}'")
        return elemento

    def _texto(self, padre: ET.Element, nombre: str) -> str:
        return self._texto_de(self._elemento(padre, nombre), nombre)

    @staticmethod
    def _texto_de(elemento: ET.Element, nombre: str) -> str:
        texto = (elemento.text or "").strip()
        if not texto:
            raise SolicitudDePartnerInvalidaError(f"El elemento '{nombre}' está vacío")
        return texto

    @staticmethod
    def _atributo(elemento: ET.Element, nombre: str) -> str:
        valor = (elemento.get(nombre) or "").strip()
        if not valor:
            raise SolicitudDePartnerInvalidaError(f"Falta el atributo obligatorio '{nombre}'")
        return valor

    @staticmethod
    def _hijo(padre: ET.Element, nombre: str, texto: str) -> ET.Element:
        hijo = ET.SubElement(padre, f"{{{NS_BANCO}}}{nombre}")
        hijo.text = texto
        return hijo

    @staticmethod
    def _sobre(contenido: ET.Element) -> str:
        sobre = ET.Element(f"{{{NS_SOAP}}}Envelope")
        ET.SubElement(sobre, f"{{{NS_SOAP}}}Body").append(contenido)
        return ET.tostring(sobre, encoding="unicode")
