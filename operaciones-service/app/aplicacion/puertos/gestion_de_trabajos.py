from abc import ABC, abstractmethod

from app.aplicacion.dtos import SolicitudDeCreacionDeTrabajo


class GestionDeTrabajos(ABC):
    """Puerto de salida hacia GestionDeTrabajosBC.

    OperacionesBC no crea trabajos: le pide a GestionDeTrabajosBC que lo haga y se entera
    del resultado por los eventos que este publica. El agregado `Trabajo` vive allá y aquí
    solo se referencia por su identificador.
    """

    @abstractmethod
    def solicitar_creacion(self, solicitud: SolicitudDeCreacionDeTrabajo) -> None:
        """Entrega la solicitud o lanza `GestionDeTrabajosNoDisponibleError`.

        Reintentar es seguro: GestionDeTrabajosBC crea un solo trabajo por referencia de
        partner.
        """

    def cerrar(self) -> None:
        """Libera conexiones al apagar el servicio. Por defecto no hay nada que liberar."""
