import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.clients import ServicioNoDisponibleError
from app.routers import sagas, trabajos, wallet

logger = logging.getLogger("bff.api")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Hogar de los Alpes - BFF",
    description=(
        "Fachada HTTP síncrona hacia las capacidades de negocio de HdA. Traduce cada "
        "solicitud externa en llamadas hacia GestionDeTrabajosBC (orquestador de la "
        "saga) y WalletBC; nunca expone directamente los tópicos de Pulsar ni el "
        "modelo interno de cada servicio."
    ),
    version="1.0.0",
)

app.include_router(trabajos.router)
app.include_router(sagas.router)
app.include_router(wallet.router)


@app.exception_handler(ServicioNoDisponibleError)
async def servicio_no_disponible(_: Request, exc: ServicioNoDisponibleError) -> JSONResponse:
    logger.error("downstream no disponible: %s", exc)
    return JSONResponse(status_code=502, content={"detalle": str(exc)})


@app.get("/salud")
def salud():
    return {"servicio": "bff", "estado": "ok"}
