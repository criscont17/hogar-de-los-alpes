from fastapi import APIRouter, HTTPException

from app import clients
from app.schemas import IniciarTrabajoRequest

router = APIRouter(prefix="/trabajos", tags=["Trabajos"])


@router.post("/completar-servicio", status_code=202)
async def completar_servicio(solicitud: IniciarTrabajoRequest):
    """Dispara la saga distribuida: crea el trabajo, retiene el pago y asigna proveedor."""
    respuesta = await clients.iniciar_saga(solicitud.model_dump(mode="json", exclude_none=True))
    if respuesta.status_code >= 400:
        raise HTTPException(status_code=respuesta.status_code, detail=clients.detalle_error(respuesta))
    return respuesta.json()


@router.get("/{trabajo_id}/estado")
async def estado_trabajo(trabajo_id: str):
    """Agrega el estado del agregado Trabajo con el de su saga (si ya se inició una)."""
    trabajo_resp = await clients.obtener_trabajo(trabajo_id)
    if trabajo_resp.status_code >= 400:
        raise HTTPException(status_code=trabajo_resp.status_code, detail=clients.detalle_error(trabajo_resp))

    # GestionDeTrabajosBC no expone una búsqueda de saga por trabajo_id, así que se
    # busca entre las sagas más recientes. Suficiente para la demo; si el volumen de
    # sagas concurrentes crece, ese filtro debería vivir en el propio servicio.
    sagas_resp = await clients.listar_sagas(limite=100)
    saga = None
    if sagas_resp.status_code < 400:
        saga = next(
            (s for s in sagas_resp.json() if s.get("trabajo_id") == trabajo_id),
            None,
        )

    return {"trabajo": trabajo_resp.json(), "saga": saga}
