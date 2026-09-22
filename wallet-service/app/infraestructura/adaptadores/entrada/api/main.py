import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.dominio.errores import (
    BilleteraDuplicadaError,
    BilleteraNoEliminableError,
    BilleteraNoEncontradaError,
    FondosInsuficientesError,
)
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.entrada.mensajeria import ConsumidorComandosWalletPulsar
from app.infraestructura.adaptadores.salida.persistencia.db import crear_tablas
from app.infraestructura.configuracion import (
    PULSAR_CONSUMIR_COMANDOS_WALLET,
    PULSAR_SUSCRIPCION_COMANDOS_WALLET,
    PULSAR_TOPICO_COMANDOS_WALLET,
    PULSAR_TOPICO_EVENTOS_WALLET,
    PULSAR_URL,
    SEMBRAR_BILLETERAS,
)
from app.infraestructura.semilla import sembrar_billeteras
from app.seedwork.dominio import DomainError

from .rutas_billetera import router
from .rutas_proveedor_wallet import router as router_proveedor

logger = logging.getLogger("wallet.api")


def crear_app(*, inicializar_db: bool = True, iniciar_mensajeria: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if inicializar_db:
            crear_tablas()
            if SEMBRAR_BILLETERAS:
                sembrar_billeteras()

        consumidor_comandos = None
        if iniciar_mensajeria and PULSAR_CONSUMIR_COMANDOS_WALLET:
            consumidor_comandos = ConsumidorComandosWalletPulsar(
                url=PULSAR_URL,
                topico_comandos=PULSAR_TOPICO_COMANDOS_WALLET,
                topico_eventos=PULSAR_TOPICO_EVENTOS_WALLET,
                suscripcion=PULSAR_SUSCRIPCION_COMANDOS_WALLET,
                procesador=contenedor.procesador_comandos_saga(),
            )
            try:
                consumidor_comandos.iniciar()
            except Exception:
                # Sin Pulsar la API REST sigue atendiendo billeteras y retiros; solo
                # no llega el paso de acreditación de la saga.
                logger.exception("no se pudo iniciar el consumidor de comandos de saga en WalletBC")
                consumidor_comandos = None

        try:
            yield
        finally:
            if consumidor_comandos is not None:
                consumidor_comandos.detener()
            if iniciar_mensajeria:
                contenedor.reiniciar()

    application = FastAPI(
        title="Hogar de los Alpes - WalletBC",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router)
    application.include_router(router_proveedor)

    @application.exception_handler(BilleteraNoEncontradaError)
    async def no_encontrada(_: Request, exc: BilleteraNoEncontradaError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detalle": str(exc)})

    @application.exception_handler(BilleteraDuplicadaError)
    async def duplicada(_: Request, exc: BilleteraDuplicadaError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detalle": str(exc)})

    @application.exception_handler(FondosInsuficientesError)
    async def fondos_insuficientes(_: Request, exc: FondosInsuficientesError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detalle": str(exc)})

    @application.exception_handler(BilleteraNoEliminableError)
    async def no_eliminable(_: Request, exc: BilleteraNoEliminableError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detalle": str(exc)})

    @application.exception_handler(DomainError)
    async def error_dominio(_: Request, exc: DomainError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detalle": str(exc)})

    @application.exception_handler(ValueError)
    async def valor_invalido(_: Request, exc: ValueError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detalle": str(exc)})

    @application.exception_handler(RequestValidationError)
    async def request_invalido(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detalle": "Solicitud inválida", "errores": jsonable_encoder(exc.errors())},
        )

    return application


logging.basicConfig(level=logging.INFO)
app = crear_app()
