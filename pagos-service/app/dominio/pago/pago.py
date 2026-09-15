from datetime import datetime, timezone

from app.dominio.errores import TransicionInvalidaError
from app.seedwork.dominio import AggregateRoot

from .dinero import Dinero
from .enums import EstadoPago, TipoPago
from .eventos import PagoConfirmado, PagoPendienteDeConciliacion, PagoRechazado
from .identificadores import PagoId


class Pago(AggregateRoot[PagoId]):
    """Un movimiento de dinero atado a un trabajo: un cobro al cliente en el
    checkout del marketplace, o un pago liberado a un proveedor cuando
    GestionDeTrabajosBC cierra el trabajo (evento `TrabajoCerradoV1`).

    No conoce el formato de ningún PSP: el caso de uso decide, a través del
    puerto `AdaptadorDePSP`, cómo se intenta el cobro/pago. El agregado solo
    protege las transiciones de estado y qué hecho corresponde a cada una.
    """

    def __init__(
        self,
        id: PagoId,
        trabajo_id: str,
        tipo: TipoPago,
        monto: Dinero,
        psp: str,
        referencia_externa: str,
        estado: EstadoPago,
        sub_trabajo_id: str | None = None,
        proveedor_id: str | None = None,
        referencia_psp: str | None = None,
        motivo: str | None = None,
        fecha_creacion: datetime | None = None,
    ) -> None:
        super().__init__()
        self.id = id
        self.trabajo_id = trabajo_id
        self.tipo = tipo
        self.monto = monto
        self.psp = psp
        self.referencia_externa = referencia_externa
        self.estado = estado
        self.sub_trabajo_id = sub_trabajo_id
        self.proveedor_id = proveedor_id
        self.referencia_psp = referencia_psp
        self.motivo = motivo
        self.fecha_creacion = fecha_creacion or datetime.now(timezone.utc)

    def confirmar(self, referencia_psp: str) -> None:
        self._exigir_pendiente()
        self.estado = EstadoPago.CONFIRMADO
        self.referencia_psp = referencia_psp
        self.motivo = None
        self.add_domain_event(
            PagoConfirmado(
                pago_id=str(self.id),
                trabajo_id=self.trabajo_id,
                sub_trabajo_id=self.sub_trabajo_id,
                proveedor_id=self.proveedor_id,
                monto=self.monto.monto,
                moneda=self.monto.moneda,
                psp=self.psp,
                referencia_psp=referencia_psp,
            )
        )

    def rechazar(self, motivo: str) -> None:
        self._exigir_pendiente()
        self.estado = EstadoPago.RECHAZADO
        self.motivo = motivo
        self.add_domain_event(
            PagoRechazado(
                pago_id=str(self.id),
                trabajo_id=self.trabajo_id,
                sub_trabajo_id=self.sub_trabajo_id,
                proveedor_id=self.proveedor_id,
                monto=self.monto.monto,
                moneda=self.monto.moneda,
                psp=self.psp,
                motivo=motivo,
            )
        )

    def marcar_pendiente_de_conciliacion(self, motivo: str) -> None:
        self._exigir_pendiente()
        self.estado = EstadoPago.PENDIENTE_CONCILIACION
        self.motivo = motivo
        self.add_domain_event(
            PagoPendienteDeConciliacion(
                pago_id=str(self.id),
                trabajo_id=self.trabajo_id,
                sub_trabajo_id=self.sub_trabajo_id,
                proveedor_id=self.proveedor_id,
                monto=self.monto.monto,
                moneda=self.monto.moneda,
                psp=self.psp,
                motivo=motivo,
            )
        )

    def _exigir_pendiente(self) -> None:
        if self.estado is not EstadoPago.PENDIENTE:
            raise TransicionInvalidaError(
                f"El pago está en estado {self.estado.value}; solo se puede resolver "
                "un pago Pendiente"
            )
