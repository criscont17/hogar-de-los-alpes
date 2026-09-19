"""Contrato público de WalletBC hacia otros bounded contexts.

Estas clases son independientes de los eventos de dominio a propósito: renombrar
un campo interno no debe romper a los consumidores. El sufijo de versión permite
publicar un esquema nuevo sin dejar de emitir el anterior.
"""

from .billetera_creada_v1 import BilleteraCreadaV1
from .billetera_eliminada_v1 import BilleteraEliminadaV1
from .debito_rechazado_v1 import DebitoRechazadoV1
from .estado_billetera_cambiado_v1 import EstadoBilleteraCambiadoV1
from .saldo_acreditado_v1 import SaldoAcreditadoV1
from .saldo_debitado_v1 import SaldoDebitadoV1

__all__ = [
    "BilleteraCreadaV1",
    "BilleteraEliminadaV1",
    "DebitoRechazadoV1",
    "EstadoBilleteraCambiadoV1",
    "SaldoAcreditadoV1",
    "SaldoDebitadoV1",
]
