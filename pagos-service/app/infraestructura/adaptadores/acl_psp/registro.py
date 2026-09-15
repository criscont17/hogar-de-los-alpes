"""Adaptadores de PSP disponibles, uno por pasarela.

Onboarding de un PSP nuevo (por ejemplo, para México) es agregar su adaptador
a esta tupla. El agregado `Pago` y `CrearPagoHandler` no cambian: es la medida
del escenario de Interoperabilidad #7 ("incorporar un nuevo PSP implica 0
cambios en el agregado Pago").
"""

from .mercadopago_argentina import MercadoPagoArgentinaAdapter
from .payu_colombia import PayUColombiaAdapter
from .wompi_colombia import WompiColombiaAdapter

ADAPTADORES_REGISTRADOS = (
    WompiColombiaAdapter,
    PayUColombiaAdapter,
    MercadoPagoArgentinaAdapter,
)
