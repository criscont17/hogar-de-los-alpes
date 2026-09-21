"""Partners con acuerdo vigente al iniciar la POC.

Equivale al onboarding contractual ya hecho para los partners que hoy tienen adaptador.
Solo se registran si no existen, así una renegociación hecha por la API no se sobrescribe.
"""

import logging
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.aplicacion.comandos import CondicionComercialSolicitada, RegistrarPartnerCommand
from app.aplicacion.puertos import UnidadDeTrabajo
from app.dominio.partner import PartnerId
from app.infraestructura import contenedor

logger = logging.getLogger("operaciones.semilla")


def _tope(clave: str, valor: str) -> CondicionComercialSolicitada:
    return CondicionComercialSolicitada(tipo="TOPE", clave=clave, valor=Decimal(valor))


def _sla(clave: str, horas: int) -> CondicionComercialSolicitada:
    return CondicionComercialSolicitada(tipo="SLA", clave=clave, valor=Decimal(horas))


PARTNERS_INICIALES: tuple[RegistrarPartnerCommand, ...] = (
    RegistrarPartnerCommand(
        partner_id="seguros-alpes",
        nombre="Seguros de los Alpes",
        pais="CO",
        red_de_proveedores=(
            "5f0c3a52-8d1e-4d7b-9a10-3c1a7e2b9d01",
            "8a4e6b13-2f7c-4c9e-b5d2-7e9f1a3c6b02",
        ),
        condiciones=(
            _tope("BASICO", "1500000"),
            _tope("PLUS", "4000000"),
            _tope("PREMIUM", "10000000"),
            _sla("CRITICA", 4),
            _sla("ALTA", 24),
            _sla("MEDIA", 72),
            _sla("BAJA", 120),
        ),
    ),
    RegistrarPartnerCommand(
        partner_id="banco-andino",
        nombre="Banco Andino",
        pais="MX",
        condiciones=(
            _tope("ORDEN", "50000"),
            _sla("1", 6),
            _sla("2", 24),
            _sla("3", 72),
            _sla("4", 168),
        ),
    ),
    RegistrarPartnerCommand(
        partner_id="muebles-hogar",
        nombre="Muebles del Hogar",
        pais="CO",
        condiciones=(
            _tope("CO", "3000000"),
            _tope("MX", "15000"),
            _sla("STANDARD", 72),
            _sla("EXPRESS", 24),
        ),
    ),
)


def sembrar_partners(
    fabrica_de_unidades: Callable[[], UnidadDeTrabajo] = contenedor.unidad_de_trabajo,
) -> None:
    for comando in PARTNERS_INICIALES:
        with fabrica_de_unidades() as uow:
            if uow.partners.obtener_por_id(PartnerId(comando.partner_id)):
                continue
        try:
            handlers = contenedor.handlers_de_comandos(fabrica_de_unidades())
            handlers[RegistrarPartnerCommand].ejecutar(comando)
        except IntegrityError:
            # Otra réplica lo registró al mismo tiempo.
            logger.info("partner %s ya registrado por otra instancia", comando.partner_id)
