from dataclasses import dataclass
from decimal import Decimal

from aplicacion.dtos import BilleteraDTO
from dominio.billetera import Dinero
from dominio.billetera.billetera_repository import BilleteraRepository
from dominio.errores import BilleteraNoEncontradaError, MonedaInvalidaError

from .acreditar_saldo import AcreditarSaldoCommand, AcreditarSaldoHandler


@dataclass(frozen=True)
class ProcesarTrabajoLiquidadoCommand:
    trabajo_id: str
    proveedor_id: str
    monto: Decimal
    moneda: str = "COP"


class ProcesarTrabajoLiquidadoHandler:
    def __init__(self, repo: BilleteraRepository, acreditar: AcreditarSaldoHandler) -> None:
        self._repo = repo
        self._acreditar = acreditar

    def ejecutar(self, comando: ProcesarTrabajoLiquidadoCommand) -> BilleteraDTO:
        billetera = self._repo.obtener_por_proveedor_id(comando.proveedor_id)
        if billetera is None:
            raise BilleteraNoEncontradaError("El proveedor no tiene una billetera")
        dinero = Dinero(comando.monto, comando.moneda)
        if dinero.moneda != billetera.saldo.moneda:
            raise MonedaInvalidaError("La moneda del evento no coincide con la billetera")
        return self._acreditar.ejecutar(
            AcreditarSaldoCommand(
                billetera_id=str(billetera.id),
                monto=dinero.monto,
                motivo="PagoDeTrabajo",
                referencia_externa=comando.trabajo_id,
            )
        )
