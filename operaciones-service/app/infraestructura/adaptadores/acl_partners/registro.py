"""Adaptadores de integración disponibles, uno por formato de partner.

Integrar un partner tiene dos partes:
1. Onboarding contractual: registrar su acuerdo con `PUT /partners/{partner_id}` (datos).
2. Integración técnica: escribir su adaptador en esta carpeta y agregarlo a esta tupla.

Nada en GestionDeTrabajosBC cambia ni se redespliega, y tampoco `app/dominio` ni
`app/aplicacion` de OperacionesBC: es la medida del escenario de Modificabilidad (#3).
"""

from .banco_andino import BancoAndinoAdapter
from .muebles_hogar import MueblesHogarAdapter
from .seguros_alpes import SegurosAlpesAdapter

ADAPTADORES_REGISTRADOS = (
    SegurosAlpesAdapter,
    BancoAndinoAdapter,
    MueblesHogarAdapter,
)
