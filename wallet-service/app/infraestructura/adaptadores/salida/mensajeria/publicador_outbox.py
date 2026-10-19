"""Relay de la bandeja de salida: lo que efectivamente publica los eventos.

Corre en un hilo de fondo, fuera de toda transacción de negocio. Cada ciclo toma
un lote de eventos pendientes, los entrega al broker y anota el resultado. Como
la fila ya está confirmada en la base, puede reintentar cuantas veces haga falta
sin riesgo para el saldo: en el peor caso un consumidor recibe el mismo evento
dos veces, y para eso el sobre lleva `event_id`.
"""

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.aplicacion.puertos import MessageBroker
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_bandeja_de_salida import (
    SqlAlchemyBandejaDeSalida,
    sobre_de,
)

logger = logging.getLogger("wallet.outbox")


@dataclass(frozen=True)
class ResultadoCiclo:
    """Lo que hizo una pasada del relay. Se devuelve para poder probarlo sin hilos."""

    publicados: int = 0
    fallidos: int = 0

    @property
    def hubo_trabajo(self) -> bool:
        return bool(self.publicados or self.fallidos)


class PublicadorOutbox:
    """Publica lo pendiente de la bandeja de salida, una pasada por intervalo."""

    def __init__(
        self,
        fabrica_de_sesiones: Callable[[], Session],
        broker: MessageBroker,
        *,
        intervalo_segundos: float = 1.0,
        lote: int = 50,
        max_intentos: int = 5,
        espera_base_segundos: float = 2.0,
    ) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones
        self._broker = broker
        self._intervalo = intervalo_segundos
        self._lote = lote
        self._max_intentos = max_intentos
        self._espera_base = espera_base_segundos
        self._detener = threading.Event()
        self._hilo: threading.Thread | None = None

    def iniciar(self) -> None:
        if self._hilo is not None:
            return
        self._detener.clear()
        self._hilo = threading.Thread(
            target=self._bucle, daemon=True, name="wallet-outbox-relay"
        )
        self._hilo.start()
        logger.info(
            "relay de la bandeja de salida iniciado (intervalo=%ss lote=%s max_intentos=%s)",
            self._intervalo,
            self._lote,
            self._max_intentos,
        )

    def detener(self) -> None:
        self._detener.set()
        if self._hilo is not None:
            # Una última pasada puede estar en vuelo; se le da el intervalo para cerrar.
            self._hilo.join(timeout=self._intervalo + 5)
            self._hilo = None
        self._broker.cerrar()

    def _bucle(self) -> None:
        while not self._detener.is_set():
            try:
                self.publicar_pendientes()
            except Exception:
                # Un ciclo roto no puede matar el hilo: sin relay, la bandeja se
                # llena en silencio y nadie se entera hasta que falta un evento.
                logger.exception("ciclo del relay de la bandeja de salida fallido")
            self._detener.wait(self._intervalo)

    def publicar_pendientes(self) -> ResultadoCiclo:
        """Una pasada completa. Es público para poder ejercitarlo sin levantar el hilo."""

        publicados = 0
        fallidos = 0
        with self._fabrica_de_sesiones() as sesion:
            bandeja = SqlAlchemyBandejaDeSalida(sesion)
            pendientes = bandeja.tomar_pendientes(self._lote)
            for modelo in pendientes:
                try:
                    self._broker.publicar(sobre_de(modelo))
                except Exception as exc:
                    bandeja.marcar_fallido(
                        modelo, str(exc), self._max_intentos, self._espera_base
                    )
                    fallidos += 1
                    logger.warning(
                        "no se pudo publicar %s event_id=%s (intento %s/%s): %s",
                        modelo.tipo,
                        modelo.event_id,
                        modelo.intentos,
                        self._max_intentos,
                        exc,
                    )
                    # El broker está caído: insistir con el resto del lote solo
                    # alarga el ciclo. El resto sigue PENDIENTE para la próxima.
                    break
                bandeja.marcar_publicado(modelo)
                publicados += 1
            sesion.commit()

        if publicados:
            logger.info("bandeja de salida: %s evento(s) publicados", publicados)
        return ResultadoCiclo(publicados=publicados, fallidos=fallidos)
