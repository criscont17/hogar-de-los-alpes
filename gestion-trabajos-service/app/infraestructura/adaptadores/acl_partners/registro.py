"""Partners B2B2C integrados con HdA.

Incorporar un partner es escribir su adaptador en esta carpeta y agregarlo a esta
tupla. Nada en `app/dominio` ni en `app/aplicacion` cambia: es la medida de los
escenarios de calidad de Modificabilidad (#3) e Interoperabilidad (#9).
"""

from .banco_andino import BancoAndinoAdapter
from .muebles_hogar import MueblesHogarAdapter
from .seguros_alpes import SegurosAlpesAdapter

ADAPTADORES_REGISTRADOS = (
    SegurosAlpesAdapter,
    BancoAndinoAdapter,
    MueblesHogarAdapter,
)
