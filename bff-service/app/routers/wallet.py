from fastapi import APIRouter, HTTPException

from app import clients
from app.schemas import RetiroWalletRequest

router = APIRouter(prefix="/proveedores", tags=["Wallet"])


@router.post("/{proveedor_id}/wallet/retiros")
async def solicitar_retiro(proveedor_id: str, solicitud: RetiroWalletRequest):
    """El proveedor_id es la billetera_id: en WalletBC cada proveedor tiene una sola billetera."""
    respuesta = await clients.debitar_billetera(proveedor_id, solicitud.model_dump(mode="json", exclude_none=True))
    if respuesta.status_code >= 400:
        raise HTTPException(status_code=respuesta.status_code, detail=clients.detalle_error(respuesta))
    return respuesta.json()
