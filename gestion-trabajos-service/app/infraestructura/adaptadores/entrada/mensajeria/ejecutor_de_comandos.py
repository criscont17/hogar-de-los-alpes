from collections.abc import Callable, Mapping
from typing import Any

from app.aplicacion.puertos import UnidadDeTrabajo
from app.infraestructura import contenedor

from .mapeo_comandos import TRADUCTORES_DE_COMANDOS


class ComandoDesconocidoError(ValueError):
    pass


class EjecutorDeComandos:
    """Ejecuta un comando recibido por mensajeria en su propia unidad de trabajo.

    Usa los mismos casos de uso que la API: un comando llega igual por REST o por
    Pulsar, se confirma en una sola transaccion y produce exactamente los mismos eventos.
    """

    def __init__(
        self,
        fabrica_de_unidades: Callable[[], UnidadDeTrabajo] = contenedor.unidad_de_trabajo,
    ) -> None:
        self._fabrica_de_unidades = fabrica_de_unidades

    def ejecutar(self, nombre: str | None, datos: Mapping[str, Any]) -> None:
        traducir = TRADUCTORES_DE_COMANDOS.get(nombre or "")
        if traducir is None:
            raise ComandoDesconocidoError(f"Comando no soportado: {nombre}")
        comando = traducir(datos)
        handlers = contenedor.handlers_de_comandos(self._fabrica_de_unidades())
        handlers[type(comando)].ejecutar(comando)
