import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from dominio.errores import (
    BilleteraDuplicadaError,
    BilleteraNoEncontradaError,
    FondosInsuficientesError,
)
from dominio.seedwork import DomainError
from infraestructura.adaptadores.salida.persistencia.db import crear_tablas

from .dependencias import registrar_manejadores_internos
from .rutas_billetera import router


def crear_app(*, inicializar_db: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if inicializar_db:
            crear_tablas()
        registrar_manejadores_internos()
        yield

    application = FastAPI(
        title="Hogar de los Alpes - WalletBC",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router)

    @application.exception_handler(BilleteraNoEncontradaError)
    async def no_encontrada(_: Request, exc: BilleteraNoEncontradaError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detalle": str(exc)})

    @application.exception_handler(BilleteraDuplicadaError)
    async def duplicada(_: Request, exc: BilleteraDuplicadaError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detalle": str(exc)})

    @application.exception_handler(FondosInsuficientesError)
    async def fondos_insuficientes(_: Request, exc: FondosInsuficientesError):
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
