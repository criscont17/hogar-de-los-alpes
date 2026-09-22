"""Pruebas de la Unidad de Trabajo y del paso de acreditación de la Saga en WalletBC.

Se ejecutan sobre SQLite en memoria, sin Pulsar ni PostgreSQL:

    DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests
"""

import os
import unittest
from decimal import Decimal
from uuid import uuid4

# Configurar entorno SQLite en memoria antes de importar la app
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.aplicacion.comandos import (
    AcreditarSaldoCommand,
    AcreditarSaldoHandler,
    CrearBilleteraCommand,
    CrearBilleteraHandler,
    ProcesadorComandosSagaWallet,
    RetirarSaldoProveedorCommand,
    RetirarSaldoProveedorHandler,
)
from app.dominio.billetera import BilleteraFactory, Dinero, EstadoBilletera, MotivoMovimiento
from app.dominio.billetera.eventos import AcreditacionRechazada, DebitoRechazado
from app.dominio.errores import FondosInsuficientesError
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.persistencia.db import Base
from app.infraestructura.adaptadores.salida.persistencia.modelos_orm import (
    BilleteraModel,
    MovimientoModel,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
from app.seedwork.dominio import DomainEvent
from app.seedwork.infraestructura import PoliticaDeReintentos


class EspiaDeEventos:
    """Suscriptor que solo guarda lo que recibe, para verificar qué se anunció."""

    def __init__(self) -> None:
        self.recibidos: list[DomainEvent] = []

    def manejar(self, evento: DomainEvent) -> None:
        self.recibidos.append(evento)

    def de_tipo(self, tipo: type[DomainEvent]) -> list[DomainEvent]:
        return [evento for evento in self.recibidos if isinstance(evento, tipo)]


class BaseWalletTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionTest = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        self.dispatcher = InMemoryDomainEventDispatcher()
        self.espia = EspiaDeEventos()
        self.dispatcher.suscribir(DomainEvent, self.espia)

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _crear_uow(self) -> SqlAlchemyUnidadDeTrabajo:
        return SqlAlchemyUnidadDeTrabajo(fabrica_de_sesiones=self.SessionTest)

    def _billetera_de(self, proveedor_id: str, saldo: str = "0", suspendida: bool = False):
        """Deja una billetera lista en base, con saldo y estado iniciales."""

        billetera = BilleteraFactory.crear_nueva(proveedor_id, "COP")
        if Decimal(saldo) > 0:
            billetera.acreditar(
                Dinero(Decimal(saldo), "COP"), MotivoMovimiento.AJUSTE_MANUAL, "saldo-inicial"
            )
        if suspendida:
            billetera.suspender()
        with self._crear_uow() as uow:
            uow.billeteras.guardar(billetera)
            uow.confirmar()
        billetera.pull_domain_events()
        return billetera

    def _movimientos_de(self, billetera_id) -> list[MovimientoModel]:
        with self.SessionTest() as sesion:
            return list(
                sesion.query(MovimientoModel).filter_by(billetera_id=billetera_id.valor).all()
            )

    def _saldo_de(self, billetera_id) -> Decimal:
        with self.SessionTest() as sesion:
            return sesion.query(BilleteraModel).filter_by(id=billetera_id.valor).one().saldo_monto


class TestUnidadDeTrabajoWallet(BaseWalletTest):
    def test_confirmar_persiste_saldo_y_movimiento_juntos(self) -> None:
        billetera = BilleteraFactory.crear_nueva(f"prov-{uuid4()}", "COP")
        billetera.acreditar(
            Dinero(Decimal("150000.00"), "COP"), MotivoMovimiento.AJUSTE_MANUAL, "ajuste-1"
        )

        with self._crear_uow() as uow:
            uow.billeteras.guardar(billetera)
            uow.confirmar()

        self.assertEqual(self._saldo_de(billetera.id), Decimal("150000.00"))
        self.assertEqual(len(self._movimientos_de(billetera.id)), 1)

    def test_salir_del_bloque_sin_confirmar_descarta_todo(self) -> None:
        billetera = BilleteraFactory.crear_nueva(f"prov-{uuid4()}", "COP")

        with self._crear_uow() as uow:
            uow.billeteras.guardar(billetera)
            # Salimos sin llamar a uow.confirmar()

        with self.SessionTest() as sesion:
            self.assertIsNone(sesion.get(BilleteraModel, billetera.id.valor))

    def test_excepcion_a_mitad_del_caso_de_uso_revierte_la_transaccion(self) -> None:
        """Ni el saldo ni el movimiento quedan a medias si algo falla antes de confirmar."""

        billetera = self._billetera_de(f"prov-{uuid4()}", saldo="100000.00")

        with self.assertRaises(RuntimeError):
            with self._crear_uow() as uow:
                guardada = uow.billeteras.obtener_por_id(billetera.id)
                guardada.acreditar(
                    Dinero(Decimal("50000.00"), "COP"), MotivoMovimiento.AJUSTE_MANUAL, "ajuste-2"
                )
                uow.billeteras.guardar(guardada)
                raise RuntimeError("Fallo simulado antes de confirmar")

        self.assertEqual(self._saldo_de(billetera.id), Decimal("100000.00"))
        self.assertEqual(len(self._movimientos_de(billetera.id)), 1)

    def test_crear_y_acreditar_por_los_casos_de_uso(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        creada = CrearBilleteraHandler(self._crear_uow(), self.dispatcher).ejecutar(
            CrearBilleteraCommand(proveedor_id, "COP")
        )

        resultado = AcreditarSaldoHandler(self._crear_uow(), self.dispatcher).ejecutar(
            AcreditarSaldoCommand(creada.id, Decimal("80000.00"), "PagoDeTrabajo", "trabajo-1")
        )

        self.assertEqual(resultado.saldo, Decimal("80000.00"))
        with self.SessionTest() as sesion:
            self.assertEqual(
                sesion.query(BilleteraModel).filter_by(proveedor_id=proveedor_id).count(), 1
            )


class TestRetiroDelProveedor(BaseWalletTest):
    def test_retiro_resuelve_la_billetera_por_proveedor(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id, saldo="200000.00")

        resultado = RetirarSaldoProveedorHandler(self._crear_uow(), self.dispatcher).ejecutar(
            RetirarSaldoProveedorCommand(proveedor_id, Decimal("50000.00"))
        )

        self.assertEqual(resultado.id, str(billetera.id))
        self.assertEqual(resultado.saldo, Decimal("150000.00"))
        self.assertEqual(self._saldo_de(billetera.id), Decimal("150000.00"))

    def test_retiro_sin_fondos_no_mueve_el_saldo_y_anuncia_el_rechazo(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id, saldo="10000.00")

        with self.assertRaises(FondosInsuficientesError):
            RetirarSaldoProveedorHandler(self._crear_uow(), self.dispatcher).ejecutar(
                RetirarSaldoProveedorCommand(proveedor_id, Decimal("99000.00"))
            )

        self.assertEqual(self._saldo_de(billetera.id), Decimal("10000.00"))
        self.assertEqual(len(self.espia.de_tipo(DebitoRechazado)), 1)


class TestAcreditacionDeLaSaga(BaseWalletTest):
    def setUp(self) -> None:
        super().setUp()
        self.esperas: list[float] = []
        self.politica = PoliticaDeReintentos(
            intentos=3,
            espera_inicial=0.01,
            factor=2.0,
            dormir=self.esperas.append,
        )
        self.procesador = ProcesadorComandosSagaWallet(
            fabrica_uow=self._crear_uow,
            dispatcher=self.dispatcher,
            politica=self.politica,
        )

    def _acreditar(self, proveedor_id: str, saga_id: str, **extra):
        return self.procesador.acreditar_proveedor(
            saga_id=saga_id,
            trabajo_id=f"trabajo-{saga_id}",
            proveedor_id=proveedor_id,
            monto=Decimal("120000.00"),
            moneda="COP",
            **extra,
        )

    def test_acreditacion_exitosa_suma_saldo_al_primer_intento(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id)

        resultado = self._acreditar(proveedor_id, str(uuid4()))

        self.assertTrue(resultado.exitoso)
        self.assertEqual(resultado.intentos, 1)
        self.assertEqual(resultado.saldo_resultante, Decimal("120000.00"))
        self.assertEqual(self._saldo_de(billetera.id), Decimal("120000.00"))
        self.assertEqual(self.esperas, [], "un éxito no debe esperar entre intentos")

    def test_comando_reentregado_no_acredita_dos_veces(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id)
        saga_id = str(uuid4())

        primero = self._acreditar(proveedor_id, saga_id)
        segundo = self._acreditar(proveedor_id, saga_id)

        self.assertTrue(primero.exitoso)
        self.assertTrue(segundo.exitoso)
        self.assertEqual(self._saldo_de(billetera.id), Decimal("120000.00"))
        self.assertEqual(len(self._movimientos_de(billetera.id)), 1)

    def test_billetera_bloqueada_agota_reintentos_con_backoff_creciente(self) -> None:
        """La política EN_DISPUTA: se reintenta, nunca se revierte el trabajo."""

        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id, saldo="30000.00", suspendida=True)

        resultado = self._acreditar(proveedor_id, str(uuid4()))

        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.intentos, 3)
        self.assertIn("suspendida", resultado.motivo)
        self.assertEqual(self.esperas, [0.01, 0.02], "la espera debe crecer por el factor")
        self.assertEqual(self._saldo_de(billetera.id), Decimal("30000.00"))
        self.assertEqual(
            len(self.espia.de_tipo(AcreditacionRechazada)),
            1,
            "el rechazo definitivo se anuncia una sola vez",
        )

    def test_fallo_simulado_ejercita_la_misma_ruta_de_disputa(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id)

        resultado = self._acreditar(proveedor_id, str(uuid4()), simular_fallo=True)

        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.intentos, 3)
        self.assertEqual(self._saldo_de(billetera.id), Decimal("0.00"))

    def test_fallo_permanente_no_se_reintenta(self) -> None:
        """Que el proveedor no tenga billetera no se arregla esperando."""

        resultado = self._acreditar(f"prov-inexistente-{uuid4()}", str(uuid4()))

        self.assertFalse(resultado.exitoso)
        self.assertEqual(resultado.intentos, 1)
        self.assertEqual(self.esperas, [])
        self.assertIn("no tiene una billetera", resultado.motivo)

    def test_billetera_reactivada_entre_reintentos_termina_acreditando(self) -> None:
        """El backoff existe para esto: el bloqueo se levanta y el intento siguiente entra."""

        proveedor_id = f"prov-{uuid4()}"
        billetera = self._billetera_de(proveedor_id, suspendida=True)

        def reactivar_en_la_espera(_: float) -> None:
            with self._crear_uow() as uow:
                guardada = uow.billeteras.obtener_por_proveedor_id(proveedor_id)
                guardada.reactivar()
                uow.billeteras.guardar(guardada)
                uow.confirmar()

        self.procesador = ProcesadorComandosSagaWallet(
            fabrica_uow=self._crear_uow,
            dispatcher=self.dispatcher,
            politica=PoliticaDeReintentos(
                intentos=3, espera_inicial=0.01, factor=2.0, dormir=reactivar_en_la_espera
            ),
        )

        resultado = self._acreditar(proveedor_id, str(uuid4()))

        self.assertTrue(resultado.exitoso)
        self.assertEqual(resultado.intentos, 2)
        self.assertEqual(self._saldo_de(billetera.id), Decimal("120000.00"))
        with self.SessionTest() as sesion:
            estado = sesion.get(BilleteraModel, billetera.id.valor).estado
        self.assertEqual(estado, EstadoBilletera.ACTIVA.value)


if __name__ == "__main__":
    unittest.main()
