import logging
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from app.seedwork.infraestructura import CircuitBreaker, CircuitoAbiertoError

from .mensaje import MensajeParaPartner

logger = logging.getLogger("trabajos.partners")


@dataclass(frozen=True)
class SaludDePartner:
    partner_id: str
    circuito: str
    fallos_consecutivos: int
    pendientes: int
    sincronizados: int
    degradaciones: int
    descartados: int
    ultimo_error: str | None


class SincronizadorDePartner:
    """Entrega mensajes al core de un partner sin que su falla alcance a nadie más.

    - Un hilo por partner (bulkhead): un partner lento o caído solo retrasa su
      propia cola, nunca la de los demás ni la respuesta al usuario.
    - Circuit breaker propio: tras fallos consecutivos deja de insistir y falla
      rápido, calibrado por partner porque cada uno tiene un SLA distinto.
    - Cola ordenada de pendientes: lo que no se pudo entregar queda como
      sincronización degradada y se reintenta con espera creciente, hasta el
      tiempo de recuperación del circuito, cuando el partner vuelve.

    Con `asincrono=False` procesa en el mismo hilo que encola; se usa en pruebas
    para que las aserciones no dependan de hilos.
    """

    def __init__(
        self,
        partner_id: str,
        enviar: Callable[[MensajeParaPartner], None],
        breaker: CircuitBreaker,
        *,
        asincrono: bool = True,
        max_pendientes: int = 1000,
        intervalo_reintento: float = 1.0,
        intervalo_maximo: float = 10.0,
    ) -> None:
        self.partner_id = partner_id
        self._enviar = enviar
        self._breaker = breaker
        self._asincrono = asincrono
        self._max_pendientes = max_pendientes
        self._intervalo_reintento = intervalo_reintento
        self._intervalo_maximo = max(intervalo_maximo, intervalo_reintento)
        self._pendientes: deque[MensajeParaPartner] = deque()
        self._lock = threading.Lock()
        self._procesando = threading.Lock()
        self._despertar = threading.Event()
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None
        self._sincronizados = 0
        self._degradaciones = 0
        self._descartados = 0
        self._ultimo_error: str | None = None

    def iniciar(self) -> None:
        if not self._asincrono or (self._hilo is not None and self._hilo.is_alive()):
            return
        self._detener.clear()
        self._hilo = threading.Thread(
            target=self._bucle, name=f"sync-partner-{self.partner_id}", daemon=True
        )
        self._hilo.start()

    def detener(self, espera: float = 2.0) -> None:
        self._detener.set()
        self._despertar.set()
        if self._hilo is not None:
            self._hilo.join(timeout=espera)
            self._hilo = None

    def encolar(self, mensaje: MensajeParaPartner) -> None:
        with self._lock:
            if len(self._pendientes) >= self._max_pendientes:
                descartado = self._pendientes.popleft()
                self._descartados += 1
                logger.error(
                    "partner=%s cola de sincronización llena; se descarta operacion=%s",
                    self.partner_id,
                    descartado.operacion,
                )
            self._pendientes.append(mensaje)
        if self._asincrono:
            self._despertar.set()
        else:
            self.procesar_pendientes()

    def procesar_pendientes(self) -> bool:
        """Entrega en orden y se detiene en el primer fallo. Devuelve si vació la cola."""

        with self._procesando:
            while True:
                with self._lock:
                    if not self._pendientes:
                        return True
                    mensaje = self._pendientes[0]
                try:
                    self._breaker.ejecutar(self._enviar, mensaje)
                except CircuitoAbiertoError as exc:
                    self._registrar_degradacion(mensaje, str(exc))
                    return False
                except Exception as exc:
                    self._registrar_degradacion(mensaje, repr(exc))
                    return False
                with self._lock:
                    self._pendientes.popleft()
                    self._sincronizados += 1
                logger.info(
                    "partner=%s sincronizado operacion=%s", self.partner_id, mensaje.operacion
                )

    def salud(self) -> SaludDePartner:
        with self._lock:
            return SaludDePartner(
                partner_id=self.partner_id,
                circuito=self._breaker.estado.value,
                fallos_consecutivos=self._breaker.fallos_consecutivos,
                pendientes=len(self._pendientes),
                sincronizados=self._sincronizados,
                degradaciones=self._degradaciones,
                descartados=self._descartados,
                ultimo_error=self._ultimo_error,
            )

    def _registrar_degradacion(self, mensaje: MensajeParaPartner, error: str) -> None:
        with self._lock:
            self._degradaciones += 1
            self._ultimo_error = error
            pendientes = len(self._pendientes)
        logger.warning(
            "sincronizacion_degradada partner=%s operacion=%s pendientes=%s circuito=%s error=%s",
            self.partner_id,
            mensaje.operacion,
            pendientes,
            self._breaker.estado.value,
            error,
        )

    def _bucle(self) -> None:
        espera = self._intervalo_reintento
        while not self._detener.is_set():
            self._despertar.wait(timeout=espera)
            self._despertar.clear()
            if self._detener.is_set():
                break
            if self.procesar_pendientes():
                espera = self._intervalo_reintento
                continue
            espera = min(espera * 2, self._intervalo_maximo)
            # Con el circuito abierto, cualquier intento antes de tiempo falla
            # rápido y uno tardío retrasa la recuperación: se despierta justo
            # cuando el circuito admite la llamada de prueba.
            restante = self._breaker.segundos_para_reintento()
            if restante > 0:
                espera = restante
