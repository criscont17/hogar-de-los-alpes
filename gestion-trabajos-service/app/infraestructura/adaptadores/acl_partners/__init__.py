"""Capa anti-corrupción frente a los partners B2B2C.

Vive en infraestructura porque traduce en ambos sentidos: recibe solicitudes en el
formato de cada partner (entrada) y le sincroniza novedades a su core (salida).
Todo lo específico de un partner queda en su archivo; dominio y aplicación solo
ven el puerto `AdaptadorDePartner` y el modelo canónico.
"""

from .base import AdaptadorDePartnerBase
from .catalogo import CatalogoDePartnersEnMemoria, construir_catalogo
from .cliente_simulado import ClientePartnerSimulado
from .mensaje import MensajeParaPartner
from .registro import ADAPTADORES_REGISTRADOS
from .sincronizacion import SaludDePartner, SincronizadorDePartner

__all__ = [
    "ADAPTADORES_REGISTRADOS",
    "AdaptadorDePartnerBase",
    "CatalogoDePartnersEnMemoria",
    "ClientePartnerSimulado",
    "MensajeParaPartner",
    "SaludDePartner",
    "SincronizadorDePartner",
    "construir_catalogo",
]
