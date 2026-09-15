from app.dominio.errores import PagoNoEncontradoError
from app.dominio.pago import Pago, PagoId
from app.dominio.pago.pago_repository import PagoRepository


def cargar_pago(repo: PagoRepository, pago_id: str) -> Pago:
    pago = repo.obtener_por_id(PagoId(pago_id))
    if pago is None:
        raise PagoNoEncontradoError("El pago no existe")
    return pago
