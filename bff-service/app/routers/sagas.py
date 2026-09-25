from fastapi import APIRouter, HTTPException

from app import clients

router = APIRouter(prefix="/sagas", tags=["Sagas"])


@router.get("/{saga_id}")
async def obtener_saga(saga_id: str):
    """Detalle y línea de tiempo (Saga Log) de una transacción distribuida."""
    respuesta = await clients.obtener_saga(saga_id)
    if respuesta.status_code >= 400:
        raise HTTPException(status_code=respuesta.status_code, detail=clients.detalle_error(respuesta))
    return respuesta.json()


@router.get("")
async def listar_sagas(limite: int = 20):
    respuesta = await clients.listar_sagas(limite=limite)
    if respuesta.status_code >= 400:
        raise HTTPException(status_code=respuesta.status_code, detail=clients.detalle_error(respuesta))
    return respuesta.json()
