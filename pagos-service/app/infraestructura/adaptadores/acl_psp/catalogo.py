import time
from collections.abc import Callable, Iterable

from app.aplicacion.puertos import AdaptadorDePSP, CatalogoDePSP
from app.dominio.errores import PSPNoSoportadoError
from app.seedwork.infraestructura import CircuitBreaker

from .base import AdaptadorDePSPBase
from .cliente_simulado import ClientePSPSimulado
from .registro import ADAPTADORES_REGISTRADOS


class CatalogoDePSPEnMemoria(CatalogoDePSP):
    def __init__(self) -> None:
        self._adaptadores: dict[str, AdaptadorDePSP] = {}
        self._clientes: dict[str, ClientePSPSimulado] = {}
        self._por_defecto_por_moneda: dict[str, str] = {}

    def registrar(
        self, adaptador: AdaptadorDePSP, cliente: ClientePSPSimulado, *, por_defecto: bool
    ) -> None:
        if adaptador.psp_id in self._adaptadores:
            raise ValueError(f"Adaptador de PSP registrado dos veces: {adaptador.psp_id}")
        self._adaptadores[adaptador.psp_id] = adaptador
        self._clientes[adaptador.psp_id] = cliente
        if por_defecto or adaptador.moneda not in self._por_defecto_por_moneda:
            self._por_defecto_por_moneda[adaptador.moneda] = adaptador.psp_id

    def obtener(self, psp_id: str) -> AdaptadorDePSP:
        try:
            return self._adaptadores[psp_id]
        except KeyError:
            raise PSPNoSoportadoError(f"No hay un adaptador registrado para '{psp_id}'") from None

    def tiene(self, psp_id: str) -> bool:
        return psp_id in self._adaptadores

    def psp_por_defecto(self, moneda: str) -> str:
        try:
            return self._por_defecto_por_moneda[moneda.upper()]
        except KeyError:
            raise PSPNoSoportadoError(
                f"Ningún PSP registrado procesa la moneda '{moneda}'"
            ) from None

    def cliente(self, psp_id: str) -> ClientePSPSimulado:
        self.obtener(psp_id)
        return self._clientes[psp_id]

    def psp_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adaptadores))


def construir_catalogo_psp(
    *,
    umbral_fallos: int = 3,
    tiempo_recuperacion: float = 10.0,
    adaptadores: Iterable[type[AdaptadorDePSPBase]] = ADAPTADORES_REGISTRADOS,
    reloj: Callable[[], float] = time.monotonic,
) -> CatalogoDePSPEnMemoria:
    """Un circuit breaker y un cliente por PSP.

    Ningún recurso de resiliencia se comparte: la caída de un PSP abre solo su
    propio circuito. El primer adaptador registrado para una moneda queda como
    su PSP por defecto (Wompi antes que PayU para COP, ver `registro.py`).
    """

    catalogo = CatalogoDePSPEnMemoria()
    for clase in adaptadores:
        cliente = ClientePSPSimulado(clase.PSP_ID)
        breaker = CircuitBreaker(
            f"psp:{clase.PSP_ID}",
            umbral_fallos=umbral_fallos,
            tiempo_recuperacion=tiempo_recuperacion,
            reloj=reloj,
        )
        catalogo.registrar(clase(cliente, breaker), cliente, por_defecto=False)
    return catalogo
