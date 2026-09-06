from datetime import datetime, timezone
from decimal import Decimal

from .billetera import Billetera
from .dinero import Dinero
from .enums import EstadoBilletera
from .eventos import BilleteraCreada
from .identificadores import BilleteraId


class BilleteraFactory:
    @staticmethod
    def crear_nueva(proveedor_id: str, moneda: str) -> Billetera:
        fecha = datetime.now(timezone.utc)
        billetera = Billetera(
            id=BilleteraId.nuevo(),
            proveedor_id=proveedor_id,
            saldo=Dinero(Decimal("0"), moneda),
            estado=EstadoBilletera.ACTIVA,
            movimientos=[],
            fecha_creacion=fecha,
        )
        billetera.add_domain_event(
            BilleteraCreada(
                billetera_id=str(billetera.id),
                proveedor_id=billetera.proveedor_id,
                fecha=fecha,
            )
        )
        return billetera

    crearNueva = crear_nueva
