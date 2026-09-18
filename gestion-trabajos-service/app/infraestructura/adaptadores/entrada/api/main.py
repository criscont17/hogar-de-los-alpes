import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.aplicacion.errores import ConflictoDeConcurrenciaError
from app.dominio.errores import (
    MontoMaximoExcedidoError,
    ProveedorNoPermitidoError,
    SubTrabajoNoEncontradoError,
    TrabajoDuplicadoError,
    TrabajoNoEncontradoError,
    TransicionInvalidaError,
)
from app.infraestructura import contenedor
from app.infraestructura.adaptadores.entrada.mensajeria import (
    ConsumidorDeComandosPulsar,
    EjecutorDeComandos,
)
from app.infraestructura.adaptadores.entrada.mensajeria.consumidor_eventos_saga_pulsar import (
    ConsumidorEventosSagaPulsar,
)
from app.infraestructura.adaptadores.salida.persistencia.db import crear_tablas
from app.infraestructura.configuracion import (
    PULSAR_CONSUMIR_COMANDOS,
    PULSAR_CONSUMIR_EVENTOS_SAGA,
    PULSAR_SUSCRIPCION_COMANDOS,
    PULSAR_SUSCRIPCION_SAGA,
    PULSAR_TOPICO_COMANDOS,
    PULSAR_TOPICO_EVENTOS_OPERACIONES,
    PULSAR_TOPICO_EVENTOS_PAGO,
    PULSAR_URL,
)
from app.seedwork.aplicacion import ApplicationError
from app.seedwork.dominio import DomainError

from .rutas_sagas import router as router_sagas
from .rutas_trabajos import router as router_trabajos

logger = logging.getLogger("trabajos.api")

# Starlette resuelve el handler recorriendo la jerarquía de la excepción, así que el
# error más específico gana aunque su base también esté registrada.
ERRORES_POR_CODIGO: tuple[tuple[int, tuple[type[Exception], ...]], ...] = (
    (status.HTTP_404_NOT_FOUND, (TrabajoNoEncontradoError, SubTrabajoNoEncontradoError)),
    (
        status.HTTP_409_CONFLICT,
        (
            TransicionInvalidaError,
            ProveedorNoPermitidoError,
            MontoMaximoExcedidoError,
            TrabajoDuplicadoError,
            ConflictoDeConcurrenciaError,
        ),
    ),
    (status.HTTP_400_BAD_REQUEST, (DomainError, ApplicationError, ValueError)),
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
        consumidor_saga = None
        if iniciar_mensajeria and PULSAR_CONSUMIR_COMANDOS:
            consumidor = ConsumidorDeComandosPulsar(
                PULSAR_URL,
                PULSAR_TOPICO_COMANDOS,
                PULSAR_SUSCRIPCION_COMANDOS,
                EjecutorDeComandos(),
            )
            try:
                consumidor.iniciar()
            except Exception:
                # Sin Pulsar la API REST sigue atendiendo; solo no llegan comandos.
                logger.exception("no se pudo iniciar el consumidor de comandos de Pulsar")
                consumidor = None

        if iniciar_mensajeria and PULSAR_CONSUMIR_EVENTOS_SAGA:
            orquestador = contenedor.obtener_orquestador_saga()
            consumidor_saga = ConsumidorEventosSagaPulsar(
                PULSAR_URL,
                [PULSAR_TOPICO_EVENTOS_PAGO, PULSAR_TOPICO_EVENTOS_OPERACIONES],
                PULSAR_SUSCRIPCION_SAGA,
                orquestador,
            )
            try:
                consumidor_saga.iniciar()
            except Exception:
                logger.exception("no se pudo iniciar el consumidor de eventos de saga de Pulsar")
                consumidor_saga = None

        try:
            yield
        finally:
            if consumidor is not None:
                consumidor.detener()
            if consumidor_saga is not None:
                consumidor_saga.detener()
            if iniciar_mensajeria:
                contenedor.reiniciar()

    application = FastAPI(
        title="Hogar de los Alpes - GestionDeTrabajosBC",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.include_router(router_trabajos)
    application.include_router(router_sagas)


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
