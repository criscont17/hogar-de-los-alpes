"""Contrato público de WalletBC hacia otros bounded contexts.

Estas clases son independientes de los eventos de dominio a propósito: renombrar
un campo interno no debe romper a los consumidores. El sufijo de versión permite
publicar un esquema nuevo sin dejar de emitir el anterior.
"""

from .billetera_creada_v1 import BilleteraCreadaV1
from .debito_rechazado_v1 import DebitoRechazadoV1
from .saldo_acreditado_v1 import SaldoAcreditadoV1
from .saldo_debitado_v1 import SaldoDebitadoV1

__all__ = [
    "BilleteraCreadaV1",
    "DebitoRechazadoV1",
    "SaldoAcreditadoV1",
    "SaldoDebitadoV1",
]
