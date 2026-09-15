from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.aplicacion.comandos.crear_pago import CrearPagoCommand, CrearPagoHandler
from app.aplicacion.dtos import EventoDeTrabajoRecibido
from app.aplicacion.errores import LiquidacionInvalidaError
from app.dominio.pago import TipoPago


@dataclass(frozen=True)
class ProcesarCierreDeTrabajoCommand:
    evento: EventoDeTrabajoRecibido


class ProcesarCierreDeTrabajoHandler:
    """Reacciona al hecho pivote `TrabajoCerradoV1` de GestionDeTrabajosBC.

    Por cada proveedor liquidado en el cierre crea (o recupera, si ya se
    procesó) un `PagoAProveedor`. PagosBC es Conformist con este contrato: no
    lo traduce, lo consume tal cual porque GestionDeTrabajosBC es upstream
    estable (mapa de contextos TO-BE). Si una liquidación individual falla al
    traducirse, las demás del mismo cierre igual se procesan.
    """

    def __init__(self, crear_pago: CrearPagoHandler) -> None:
        self._crear_pago = crear_pago

    def ejecutar(self, comando: ProcesarCierreDeTrabajoCommand) -> None:
        evento = comando.evento
        errores: list[str] = []
        for liquidacion in evento.liquidaciones:
            try:
                self._crear_pago.ejecutar(self._a_comando(evento, liquidacion))
            except LiquidacionInvalidaError as exc:
                errores.append(str(exc))
        if errores:
            raise LiquidacionInvalidaError(
                f"{len(errores)} liquidación(es) del trabajo {evento.trabajo_id} no se "
                f"pudieron procesar: {'; '.join(errores)}"
            )

    @staticmethod
    def _a_comando(evento: EventoDeTrabajoRecibido, liquidacion: dict) -> CrearPagoCommand:
        try:
            sub_trabajo_id = str(liquidacion["sub_trabajo_id"])
            proveedor_id = str(liquidacion["proveedor_id"])
            monto = Decimal(str(liquidacion["monto"]))
        except (KeyError, InvalidOperation, ValueError) as exc:
            raise LiquidacionInvalidaError(f"liquidación inválida {liquidacion!r}: {exc}") from exc
        return CrearPagoCommand(
            trabajo_id=evento.trabajo_id,
            tipo=TipoPago.PAGO_A_PROVEEDOR.value,
            monto=monto,
            moneda=evento.moneda,
            referencia_externa=f"{evento.trabajo_id}:{sub_trabajo_id}",
            sub_trabajo_id=sub_trabajo_id,
            proveedor_id=proveedor_id,
        )
