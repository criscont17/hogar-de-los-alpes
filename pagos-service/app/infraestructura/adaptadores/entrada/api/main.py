import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.aplicacion.errores import ConflictoDeConcurrenciaError, LiquidacionInvalidaError
from app.dominio.errores import PagoNoEncontradoError, PSPNoSoportadoError, TransicionInvalidaError
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.entrada.mensajeria import (
    ConsumidorDeEventosDeTrabajoPulsar,
    EjecutorDeEventos,
)
from app.infraestructura.adaptadores.salida.persistencia.db import crear_tablas
from app.infraestructura.configuracion import (
    PULSAR_CONSUMIR_EVENTOS_TRABAJO,
    PULSAR_SUSCRIPCION_EVENTOS_TRABAJO,
    PULSAR_TOPICO_EVENTOS_TRABAJO,
    PULSAR_URL,
)
from app.seedwork.aplicacion import ApplicationError
from app.seedwork.dominio import DomainError

from .rutas_pagos import router as router_pagos

logger = logging.getLogger("pagos.api")

# Starlette resuelve el handler recorriendo la jerarquía de la excepción, así que el
# error más específico gana aunque su base también esté registrada.
ERRORES_POR_CODIGO: tuple[tuple[int, tuple[type[Exception], ...]], ...] = (
    (status.HTTP_404_NOT_FOUND, (PagoNoEncontradoError,)),
    (
        status.HTTP_409_CONFLICT,
        (TransicionInvalidaError, ConflictoDeConcurrenciaError),
    ),
    (
        status.HTTP_400_BAD_REQUEST,
        (PSPNoSoportadoError, LiquidacionInvalidaError, DomainError, ApplicationError, ValueError),
    ),
)


def _responder_con(codigo: int):
    async def manejar(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=codigo, content={"detalle": str(exc)})

    return manejar


def crear_app(*, inicializar_db: bool = True, iniciar_mensajeria: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if inicializar_db:
            crear_tablas()
        consumidor = None
        if iniciar_mensajeria and PULSAR_CONSUMIR_EVENTOS_TRABAJO:
            consumidor = ConsumidorDeEventosDeTrabajoPulsar(
                PULSAR_URL,
                PULSAR_TOPICO_EVENTOS_TRABAJO,
                PULSAR_SUSCRIPCION_EVENTOS_TRABAJO,
                EjecutorDeEventos(),
            )
            try:
                consumidor.iniciar()
            except Exception:
                # Sin Pulsar la API REST sigue atendiendo el checkout; solo no
                # llegan los cierres de trabajo que liberan pagos a proveedores.
                logger.exception("no se pudo iniciar el consumidor de eventos de Pulsar")
                consumidor = None
        try:
            yield
        finally:
            if consumidor is not None:
                consumidor.detener()
            if iniciar_mensajeria:
                contenedor.reiniciar()

    application = FastAPI(
        title="Hogar de los Alpes - PagosBC",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router_pagos)

    for codigo, errores in ERRORES_POR_CODIGO:
        for error in errores:
            application.add_exception_handler(error, _responder_con(codigo))

    @application.exception_handler(RequestValidationError)
    async def request_invalido(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detalle": "Solicitud inválida", "errores": jsonable_encoder(exc.errors())},
        )

    return application


logging.basicConfig(level=logging.INFO)
app = crear_app()
