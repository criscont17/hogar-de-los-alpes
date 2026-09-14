import time
from collections.abc import Callable, Iterable

from app.aplicacion.errores import PartnerNoRegistradoError
from app.aplicacion.puertos import AdaptadorDePartner, CatalogoDePartners
from app.seedwork.infraestructura import CircuitBreaker

from .base import AdaptadorDePartnerBase
from .cliente_simulado import ClientePartnerSimulado
from .registro import ADAPTADORES_REGISTRADOS
from .sincronizacion import SincronizadorDePartner


class CatalogoDePartnersEnMemoria(CatalogoDePartners):
    def __init__(self) -> None:
        self._adaptadores: dict[str, AdaptadorDePartner] = {}
        self._sincronizadores: dict[str, SincronizadorDePartner] = {}
        self._clientes: dict[str, ClientePartnerSimulado] = {}

    def registrar(
        self,
        adaptador: AdaptadorDePartner,
        sincronizador: SincronizadorDePartner,
        cliente: ClientePartnerSimulado,
    ) -> None:
        if adaptador.partner_id in self._adaptadores:
            raise ValueError(f"Partner registrado dos veces: {adaptador.partner_id}")
        self._adaptadores[adaptador.partner_id] = adaptador
        self._sincronizadores[adaptador.partner_id] = sincronizador
        self._clientes[adaptador.partner_id] = cliente

    def obtener(self, partner_id: str) -> AdaptadorDePartner:
        try:
            return self._adaptadores[partner_id]
        except KeyError:
            raise PartnerNoRegistradoError(
                f"El partner '{partner_id}' no está integrado con HdA"
            ) from None

    def partner_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adaptadores))

    def sincronizador(self, partner_id: str) -> SincronizadorDePartner:
        self.obtener(partner_id)
        return self._sincronizadores[partner_id]

    def cliente(self, partner_id: str) -> ClientePartnerSimulado:
        self.obtener(partner_id)
        return self._clientes[partner_id]

    def iniciar(self) -> None:
        for sincronizador in self._sincronizadores.values():
            sincronizador.iniciar()

    def detener(self) -> None:
        for sincronizador in self._sincronizadores.values():
            sincronizador.detener()


def construir_catalogo(
    *,
    asincrono: bool = True,
    umbral_fallos: int = 3,
    tiempo_recuperacion: float = 10.0,
    adaptadores: Iterable[type[AdaptadorDePartnerBase]] = ADAPTADORES_REGISTRADOS,
    reloj: Callable[[], float] = time.monotonic,
) -> CatalogoDePartnersEnMemoria:
    """Un circuit breaker, un sincronizador y un cliente por partner.

    Ningún recurso de resiliencia se comparte: la caída de un partner abre solo
    su circuito y acumula pendientes solo en su cola.
    """

    catalogo = CatalogoDePartnersEnMemoria()
    for clase in adaptadores:
        cliente = ClientePartnerSimulado(clase.PARTNER_ID)
        breaker = CircuitBreaker(
            f"partner:{clase.PARTNER_ID}",
            umbral_fallos=umbral_fallos,
            tiempo_recuperacion=tiempo_recuperacion,
            reloj=reloj,
        )
        sincronizador = SincronizadorDePartner(
            clase.PARTNER_ID,
            cliente.enviar,
            breaker,
            asincrono=asincrono,
            intervalo_maximo=tiempo_recuperacion,
        )
        catalogo.registrar(clase(sincronizador), sincronizador, cliente)
    return catalogo
