import os
import unittest
from decimal import Decimal
from uuid import uuid4

# Configurar entorno SQLite en memoria antes de importar la app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.aplicacion.comandos import CrearPagoCommand, CrearPagoHandler
from app.aplicacion.dtos import PagoDTO
from app.dominio.pago import Dinero, EstadoPago, PagoFactory, TipoPago
from app.infraestructura.adaptadores.acl_psp import construir_catalogo_psp
from app.infraestructura.adaptadores.entrada.api.dependencias import (
    obtener_crear_handler,
    obtener_handlers_de_comandos,
    obtener_repo,
    obtener_unidad_de_trabajo,
)
from app.infraestructura.adaptadores.entrada.api.main import app
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.persistencia.db import Base
from app.infraestructura.adaptadores.salida.persistencia.modelos_orm import PagoModel
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_pago_repository import (
    SqlAlchemyPagoRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)


class TestUnidadDeTrabajoPagos(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionTest = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        self.catalogo_psp = construir_catalogo_psp()
        self.dispatcher = InMemoryDomainEventDispatcher()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _crear_uow(self) -> SqlAlchemyUnidadDeTrabajo:
        return SqlAlchemyUnidadDeTrabajo(fabrica_de_sesiones=self.SessionTest)

    def test_uow_commit_persiste_correctamente(self) -> None:
        ref = f"ref-{uuid4()}"
        pago = PagoFactory.crear(
            trabajo_id="trabajo-1",
            tipo=TipoPago.COBRO_CLIENTE,
            monto=Dinero(Decimal("150000.00"), "COP"),
            psp="wompi-colombia",
            referencia_externa=ref,
        )

        uow = self._crear_uow()
        with uow:
            uow.pagos.guardar(pago)
            uow.confirmar()

        with self.SessionTest() as sesion:
            guardado = sesion.query(PagoModel).filter_by(referencia_externa=ref).first()
            self.assertIsNotNone(guardado)
            self.assertEqual(guardado.trabajo_id, "trabajo-1")
            self.assertEqual(guardado.monto, Decimal("150000.00"))

    def test_uow_rollback_descarta_cambios_si_no_se_confirma(self) -> None:
        ref = f"ref-no-commit-{uuid4()}"
        pago = PagoFactory.crear(
            trabajo_id="trabajo-2",
            tipo=TipoPago.COBRO_CLIENTE,
            monto=Dinero(Decimal("80000.00"), "COP"),
            psp="wompi-colombia",
            referencia_externa=ref,
        )

        uow = self._crear_uow()
        with uow:
            uow.pagos.guardar(pago)
            # Salimos sin llamar a uow.confirmar()

        with self.SessionTest() as sesion:
            guardado = sesion.query(PagoModel).filter_by(referencia_externa=ref).first()
            self.assertIsNone(guardado, "El pago no debe existir si no se llamó confirmar()")

    def test_uow_excepcion_revierte_automaticamente(self) -> None:
        ref = f"ref-error-{uuid4()}"
        pago = PagoFactory.crear(
            trabajo_id="trabajo-3",
            tipo=TipoPago.COBRO_CLIENTE,
            monto=Dinero(Decimal("95000.00"), "COP"),
            psp="wompi-colombia",
            referencia_externa=ref,
        )

        uow = self._crear_uow()
        with self.assertRaises(RuntimeError):
            with uow:
                uow.pagos.guardar(pago)
                raise RuntimeError("Fallo simulado antes de confirmar")
                uow.confirmar()

        with self.SessionTest() as sesion:
            guardado = sesion.query(PagoModel).filter_by(referencia_externa=ref).first()
            self.assertIsNone(guardado, "La transacción debió revertirse ante una excepción")

    def test_crear_pago_handler_con_uow_happy_path(self) -> None:
        uow = self._crear_uow()
        handler = CrearPagoHandler(
            uow=uow,
            dispatcher=self.dispatcher,
            adaptadores=self.catalogo_psp,
        )

        ref = f"ref-handler-{uuid4()}"
        comando = CrearPagoCommand(
            trabajo_id="trabajo-4",
            tipo=TipoPago.COBRO_CLIENTE.value,
            monto=Decimal("120000.00"),
            moneda="COP",
            referencia_externa=ref,
            psp="wompi-colombia",
        )

        resultado = handler.ejecutar(comando)
        self.assertIsInstance(resultado, PagoDTO)
        self.assertEqual(resultado.referencia_externa, ref)
        self.assertEqual(resultado.estado, EstadoPago.CONFIRMADO.value)

        # Verificar persistencia en base de datos
        with self.SessionTest() as sesion:
            guardado = sesion.query(PagoModel).filter_by(referencia_externa=ref).first()
            self.assertIsNotNone(guardado)
            self.assertEqual(guardado.estado, EstadoPago.CONFIRMADO.value)

    def test_crear_pago_handler_idempotencia(self) -> None:
        uow = self._crear_uow()
        handler = CrearPagoHandler(
            uow=uow,
            dispatcher=self.dispatcher,
            adaptadores=self.catalogo_psp,
        )

        ref = f"ref-idemp-{uuid4()}"
        comando = CrearPagoCommand(
            trabajo_id="trabajo-5",
            tipo=TipoPago.COBRO_CLIENTE.value,
            monto=Decimal("50000.00"),
            moneda="COP",
            referencia_externa=ref,
            psp="wompi-colombia",
        )

        primer_resultado = handler.ejecutar(comando)
        segundo_resultado = handler.ejecutar(comando)

        self.assertEqual(primer_resultado.id, segundo_resultado.id)
        self.assertEqual(primer_resultado.referencia_externa, segundo_resultado.referencia_externa)

        with self.SessionTest() as sesion:
            conteo = sesion.query(PagoModel).filter_by(referencia_externa=ref).count()
            self.assertEqual(conteo, 1, "No debe haber duplicados para la misma referencia")

    def test_api_rest_post_pagos_con_uow(self) -> None:
        def override_uow():
            return self._crear_uow()

        def override_repo():
            sesion = self.SessionTest()
            return SqlAlchemyPagoRepository(sesion)

        app.dependency_overrides[obtener_unidad_de_trabajo] = override_uow
        app.dependency_overrides[obtener_repo] = override_repo

        client = TestClient(app)
        ref = f"ref-api-{uuid4()}"
        payload = {
            "trabajo_id": "trabajo-api-1",
            "monto": 250000.00,
            "moneda": "COP",
            "referencia_externa": ref,
            "psp": "wompi-colombia",
        }

        response = client.post("/pagos", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["trabajo_id"], "trabajo-api-1")
        self.assertEqual(data["estado"], "Confirmado")

        app.dependency_overrides.clear()


if __name__ == "__main__":
    unittest.main()
