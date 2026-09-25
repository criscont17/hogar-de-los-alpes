"""Adaptador de Banco Andino: banco mexicano que integra por SOAP (XML).

Solo traduce formato. El tope máximo por orden y el SLA de cada nivel de urgencia están en
el acuerdo comercial del partner (agregado `Partner`).

Particularidades del formato:
- La orden se identifica por `IdOrden` y trae el tope que el banco autoriza para ella; el
  acuerdo verifica que no supere lo pactado.
- Las actividades se agrupan por `etapa`: lo de una misma etapa va en paralelo y cada etapa
  espera a que termine completa la anterior.
- `NivelUrgencia` numérico (1 = crítica ... 4 = baja) es la clave del SLA en el acuerdo.
- Solo quiere enterarse de cierres, cancelaciones, cotizaciones rechazadas y órdenes
  rechazadas.

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
    EstadoTrabajoDePartner,
    EventoDeTrabajoRecibido,
    RespuestaDePartner,
    SolicitudDePartner,
    SubTrabajoSolicitado,
    TrabajoDePartnerDTO,
)
from app.aplicacion.errores import SolicitudDePartnerInvalidaError

from .base import AdaptadorDePartnerBase, decimal, traducir_valor
from .mensaje import MensajeParaPartner

MEDIA_TYPE = "text/xml"
NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_BANCO = "urn:bancoandino:hogar:v3"
NS = {"soapenv": NS_SOAP, "ba": NS_BANCO}

ET.register_namespace("soapenv", NS_SOAP)
ET.register_namespace("ba", NS_BANCO)

CATEGORIA_POR_OFICIO = {
    "FONTANERIA": "Plomeria",
    "ELECTRICIDAD": "Electricidad",
    "CARPINTERIA": "Carpinteria",
    "PINTURA": "Pintura",
    "AZULEJO": "Baldoseria",
}

URGENCIA_POR_NIVEL = {"1": "Emergencia", "2": "Alta", "3": "Media", "4": "Baja"}

ESTADO_PARA_EL_PARTNER = {
    EstadoTrabajoDePartner.SOLICITADO: "RECIBIDA",
    EstadoTrabajoDePartner.CREADO: "REGISTRADA",
    EstadoTrabajoDePartner.EN_EJECUCION: "EN_PROCESO",
    EstadoTrabajoDePartner.CERRADO: "CONCLUIDA",
    EstadoTrabajoDePartner.CANCELADO: "CANCELADA",
    EstadoTrabajoDePartner.RECHAZADO: "RECHAZADA",
}

OPERACION_POR_EVENTO = {
    "TrabajoCerradoV1": "NotificarConclusionOrden",
    "TrabajoCanceladoV1": "NotificarCancelacionOrden",
    "AsignacionRechazadaV1": "NotificarCotizacionRechazada",
    "CreacionDeTrabajoRechazadaV1": "NotificarRechazoOrden",
}


class BancoAndinoAdapter(AdaptadorDePartnerBase):
    PARTNER_ID = "banco-andino"

    def traducir_solicitud(self, contenido: str) -> SolicitudDePartner:
        if "<!DOCTYPE" in contenido.upper():
            # SOAP no admite DTD; rechazarla evita ataques de expansión de entidades.
            raise SolicitudDePartnerInvalidaError("La solicitud SOAP no puede declarar una DTD")
        try:
            raiz = ET.fromstring(contenido)
        except ET.ParseError as exc:
            raise SolicitudDePartnerInvalidaError(f"XML mal formado: {exc}") from exc
        orden = raiz.find("soapenv:Body/ba:SolicitudOrdenServicio", NS)
        if orden is None:
            raise SolicitudDePartnerInvalidaError("El sobre SOAP no contiene SolicitudOrdenServicio")

        inmueble = self._elemento(orden, "Inmueble")
        tope = self._elemento(orden, "TopeAutorizado")
        nivel = self._texto(orden, "NivelUrgencia")
        return SolicitudDePartner(
            referencia_externa=self._texto(orden, "IdOrden"),
            descripcion=self._texto(orden, "Resumen"),
            urgencia=traducir_valor(URGENCIA_POR_NIVEL, nivel, "Nivel de urgencia"),
            pais=self._atributo(inmueble, "pais"),
            ciudad=self._atributo(inmueble, "ciudad"),
            direccion=self._texto_de(inmueble, "Inmueble"),
            moneda=self._atributo(tope, "moneda"),
            sub_trabajos=self._actividades(orden),
            clave_sla=nivel,
            clave_tope="ORDEN",
            tope_solicitado=decimal(tope.text, "TopeAutorizado"),
        )

    def traducir_estado(self, trabajo: TrabajoDePartnerDTO) -> RespuestaDePartner:
        estado = ET.Element(f"{{{NS_BANCO}}}EstadoOrdenServicio")
        self._hijo(estado, "IdOrden", trabajo.referencia_externa)
        self._hijo(estado, "FolioHdA", trabajo.trabajo_id or "")
        self._hijo(estado, "Estado", ESTADO_PARA_EL_PARTNER[trabajo.estado])
        terminadas = sum(1 for sub in trabajo.sub_trabajos if sub.estado == "Completado")
        self._hijo(estado, "ActividadesTerminadas", str(terminadas))
        self._hijo(estado, "ActividadesTotales", str(len(trabajo.sub_trabajos)))
        self._hijo(estado, "MontoEjercido", str(trabajo.costo_total)).set("moneda", trabajo.moneda or "")
        if trabajo.motivo_rechazo:
            self._hijo(estado, "Motivo", trabajo.motivo_rechazo)
        return RespuestaDePartner(self._sobre(estado), MEDIA_TYPE)

    def traducir_evento(self, evento: EventoDeTrabajoRecibido) -> MensajeParaPartner | None:
        operacion = OPERACION_POR_EVENTO.get(evento.nombre)
        if operacion is None:
            return None
        datos = evento.datos
        notificacion = ET.Element(f"{{{NS_BANCO}}}{operacion}")
        self._hijo(notificacion, "IdOrden", evento.referencia_externa or "")
        self._hijo(notificacion, "Fecha", evento.occurred_at)
        if evento.nombre == "TrabajoCerradoV1":
            self._hijo(notificacion, "MontoFinal", datos["costo_total"]).set("moneda", datos["moneda"])
        elif evento.nombre == "AsignacionRechazadaV1":
            self._hijo(notificacion, "MontoCotizado", datos["monto_cotizado"]).set("moneda", datos["moneda"])
            self._hijo(notificacion, "Motivo", datos["motivo_rechazo"])
        else:
            self._hijo(notificacion, "Motivo", datos["motivo"])
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
                        categoria=traducir_valor(CATEGORIA_POR_OFICIO, oficio, "Oficio"),
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
