from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.infraestructura import contenedor
from app.infraestructura.adaptadores.salida.persistencia.db import SessionLocal

from .mapeo_comandos import TRADUCTORES_DE_COMANDOS


class ComandoDesconocidoError(ValueError):
    pass


class EjecutorDeComandos:
    """Ejecuta un comando recibido por mensajería con una sesión de base de datos propia.

    Usa los mismos casos de uso que la API: un comando llega igual por REST o por
    Pulsar y produce exactamente los mismos eventos.
    """

    def __init__(self, fabrica_de_sesiones: Callable[[], Session] = SessionLocal) -> None:
        self._fabrica_de_sesiones = fabrica_de_sesiones

    def ejecutar(self, nombre: str | None, datos: Mapping[str, Any]) -> None:
        traducir = TRADUCTORES_DE_COMANDOS.get(nombre or "")
        if traducir is None:
            raise ComandoDesconocidoError(f"Comando no soportado: {nombre}")
        comando = traducir(datos)
        with self._fabrica_de_sesiones() as session:
            contenedor.handlers_de_comandos(session)[type(comando)].ejecutar(comando)
