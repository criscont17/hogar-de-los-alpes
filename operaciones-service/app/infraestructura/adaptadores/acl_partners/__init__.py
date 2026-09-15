"""Capa anti-corrupción frente a los partners B2B2C.

Traduce en ambos sentidos: recibe solicitudes en el formato de cada partner y le entrega
las novedades de sus trabajos en ese mismo formato. Todo lo específico del formato de un
partner queda en su archivo; sus reglas comerciales están en su `AcuerdoComercial`.
"""

from .base import AdaptadorDePartnerBase
from .catalogo import CatalogoDeAdaptadoresEnMemoria, construir_catalogo
from .cliente_simulado import ClientePartnerSimulado
from .mensaje import MensajeParaPartner
from .registro import ADAPTADORES_REGISTRADOS
from .sincronizacion import SaludDePartner, SincronizadorDePartner

__all__ = [
    "ADAPTADORES_REGISTRADOS",
    "AdaptadorDePartnerBase",
    "CatalogoDeAdaptadoresEnMemoria",
    "ClientePartnerSimulado",
    "MensajeParaPartner",
    "SaludDePartner",
    "SincronizadorDePartner",
    "construir_catalogo",
]
