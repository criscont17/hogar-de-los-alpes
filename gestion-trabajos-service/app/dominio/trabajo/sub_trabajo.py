from collections.abc import Iterable

from app.dominio.errores import (
    DatosDelTrabajoInvalidosError,
    EvidenciaRequeridaError,
    FlujoInvalidoError,
    SubTrabajoBloqueadoError,
    TransicionInvalidaError,
)
from app.seedwork.dominio import Entity

from .dinero import Dinero
from .enums import Categoria, EstadoSubTrabajo
from .identificadores import SubTrabajoId


class SubTrabajo(Entity[SubTrabajoId]):
    """Parte de un trabajo con su propia categoría, proveedor y cotización.

    Sus transiciones solo las invoca el agregado `Trabajo`, que es quien conoce el
    grafo completo y puede decidir cuándo se levanta un bloqueo.
    """

    def __init__(
        self,
        id: SubTrabajoId,
        categoria: Categoria,
        descripcion: str,
        depende_de: Iterable[SubTrabajoId],
        estado: EstadoSubTrabajo,
        proveedor_id: str | None = None,
        monto_cotizado: Dinero | None = None,
        evidencias: Iterable[str] = (),
    ) -> None:
        descripcion = (descripcion or "").strip()
        if not descripcion:
            raise DatosDelTrabajoInvalidosError("La descripción del sub-trabajo es obligatoria")
        self.id = id
        self.categoria = categoria
        self.descripcion = descripcion
        self._depende_de = frozenset(depende_de)
        if id in self._depende_de:
            raise FlujoInvalidoError("Un sub-trabajo no puede depender de sí mismo")
        self._estado = estado
        self._proveedor_id = proveedor_id
        self._monto_cotizado = monto_cotizado
        self._evidencias = tuple(evidencias)

    @property
    def depende_de(self) -> frozenset[SubTrabajoId]:
        return self._depende_de

    @property
    def estado(self) -> EstadoSubTrabajo:
        return self._estado

    @property
    def proveedor_id(self) -> str | None:
        return self._proveedor_id

    @property
    def monto_cotizado(self) -> Dinero | None:
        return self._monto_cotizado

    @property
    def evidencias(self) -> tuple[str, ...]:
        return self._evidencias

    def exigir_asignable(self) -> None:
        if self._estado is EstadoSubTrabajo.BLOQUEADO:
            raise SubTrabajoBloqueadoError(
                "El sub-trabajo espera a que terminen sus dependencias"
            )
        if self._estado not in (EstadoSubTrabajo.PENDIENTE, EstadoSubTrabajo.ASIGNADO):
            raise TransicionInvalidaError(
                f"No se puede asignar proveedor a un sub-trabajo {self._estado.value}"
            )

    def asignar(self, proveedor_id: str, monto_cotizado: Dinero) -> None:
        self.exigir_asignable()
        self._proveedor_id = proveedor_id
        self._monto_cotizado = monto_cotizado
        self._estado = EstadoSubTrabajo.ASIGNADO

    def iniciar(self) -> None:
        if self._estado is EstadoSubTrabajo.BLOQUEADO:
            raise SubTrabajoBloqueadoError(
                "El sub-trabajo no puede iniciarse mientras sus dependencias no terminen"
            )
        if self._estado is not EstadoSubTrabajo.ASIGNADO:
            raise TransicionInvalidaError(
                "Solo un sub-trabajo con proveedor asignado puede iniciarse"
            )
        self._estado = EstadoSubTrabajo.EN_EJECUCION

    def completar(self, evidencias: Iterable[str]) -> None:
        if self._estado is not EstadoSubTrabajo.EN_EJECUCION:
            raise TransicionInvalidaError("Solo un sub-trabajo en ejecución puede completarse")
        limpias = tuple(evidencia.strip() for evidencia in evidencias if evidencia and evidencia.strip())
        if not limpias:
            raise EvidenciaRequeridaError("Completar un sub-trabajo exige al menos una evidencia")
        self._evidencias = limpias
        self._estado = EstadoSubTrabajo.COMPLETADO

    def exigir_congelable(self) -> None:
        if self._estado in (
            EstadoSubTrabajo.EN_EJECUCION,
            EstadoSubTrabajo.COMPLETADO,
            EstadoSubTrabajo.CANCELADO,
        ):
            raise TransicionInvalidaError(
                f"El sub-trabajo {self.id} ya inició o finalizó; no puede quedar bloqueado"
            )

    def congelar_hasta(self, otro: SubTrabajoId) -> None:
        """Agrega una dependencia descubierta en plena ejecución (re-diagnóstico)."""

        self.exigir_congelable()
        self._depende_de = self._depende_de | {otro}
        self._estado = EstadoSubTrabajo.BLOQUEADO

    def desbloquear(self) -> None:
        # Si ya tenía proveedor antes de congelarse, lo conserva: el bloqueo no
        # invalida la asignación, solo la pospone.
        self._estado = (
            EstadoSubTrabajo.ASIGNADO if self._proveedor_id else EstadoSubTrabajo.PENDIENTE
        )

    def cancelar(self) -> None:
        if self._estado not in (EstadoSubTrabajo.COMPLETADO, EstadoSubTrabajo.CANCELADO):
            self._estado = EstadoSubTrabajo.CANCELADO
