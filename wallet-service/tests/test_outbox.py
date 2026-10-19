"""Pruebas de la bandeja de salida (patrón Outbox) de WalletBC.

Se ejecutan sobre SQLite en memoria, sin Pulsar ni PostgreSQL:

    DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests

Lo que se verifica es la promesa del patrón: el evento se guarda con la misma
transacción que el saldo, y se publica después, tantas veces como haga falta.
"""

import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.aplicacion.comandos import (
    AcreditarSaldoCommand,
    AcreditarSaldoHandler,
    ProcesadorComandosSagaWallet,
    RetirarSaldoProveedorCommand,
    RetirarSaldoProveedorHandler,
)
from app.dominio.billetera import BilleteraFactory, Dinero, MotivoMovimiento
from app.dominio.errores import FondosInsuficientesError
from app.infraestructura.adaptadores.salida.eventos import InMemoryDomainEventDispatcher
from app.infraestructura.adaptadores.salida.mensajeria import (
    InMemoryMessageBroker,
    PublicadorOutbox,
    PulsarMessageBroker,
)
from app.seedwork.aplicacion import SobreDeEvento
from app.infraestructura.adaptadores.salida.persistencia.db import Base
from app.infraestructura.adaptadores.salida.persistencia.modelos_orm import (
    EventoSalienteModel,
    MovimientoModel,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_bandeja_de_salida import (
    SqlAlchemyBandejaDeSalida,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_unidad_de_trabajo import (
    SqlAlchemyUnidadDeTrabajo,
)
from app.seedwork.dominio import DomainEvent
from app.seedwork.infraestructura import PoliticaDeReintentos


class BaseOutboxTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.SessionTest = sessionmaker(bind=self.engine, expire_on_commit=False, class_=Session)
        self.dispatcher = InMemoryDomainEventDispatcher()
        self.dispatcher.suscribir(DomainEvent, _EspiaSilenciosa())
        self.broker = InMemoryMessageBroker()

    def tearDown(self) -> None:
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _crear_uow(self) -> SqlAlchemyUnidadDeTrabajo:
        return SqlAlchemyUnidadDeTrabajo(fabrica_de_sesiones=self.SessionTest)

    def _relay(self, *, max_intentos: int = 5, espera_base: float = 0.0) -> PublicadorOutbox:
        return PublicadorOutbox(
            fabrica_de_sesiones=self.SessionTest,
            broker=self.broker,
            lote=50,
            max_intentos=max_intentos,
            espera_base_segundos=espera_base,
        )

    def _billetera_de(self, proveedor_id: str, saldo: str = "0", suspendida: bool = False):
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
        # La siembra directa no pasa por un caso de uso: la bandeja arranca vacía.
        self._vaciar_bandeja()
        return billetera

    def _vaciar_bandeja(self) -> None:
        with self.SessionTest() as sesion:
            for fila in sesion.scalars(select(EventoSalienteModel)):
                sesion.delete(fila)
            sesion.commit()

    def _eventos(self, estado: str | None = None) -> list[EventoSalienteModel]:
        with self.SessionTest() as sesion:
            return SqlAlchemyBandejaDeSalida(sesion).listar(estado=estado, limite=100)

    def _acreditar(self, billetera_id: str, referencia: str = "trabajo-1") -> None:
        AcreditarSaldoHandler(self._crear_uow(), self.dispatcher).ejecutar(
            AcreditarSaldoCommand(billetera_id, Decimal("80000.00"), "PagoDeTrabajo", referencia)
        )


class _EspiaSilenciosa:
    """El bus necesita al menos un suscriptor para no advertir en cada evento."""

    def manejar(self, evento: DomainEvent) -> None:
        return None


class TestEscrituraTransaccional(BaseOutboxTest):
    """La mitad del patrón que da la garantía: encolar dentro de la transacción."""

    def test_el_caso_de_uso_deja_el_evento_pendiente(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")

        self._acreditar(str(billetera.id))

        pendientes = self._eventos("PENDIENTE")
        self.assertEqual(len(pendientes), 1)
        self.assertEqual(pendientes[0].tipo, "SaldoAcreditadoV1")
        self.assertEqual(pendientes[0].intentos, 0)
        self.assertEqual(
            pendientes[0].clave_particion,
            str(billetera.id),
            "la clave de partición agrupa por billetera",
        )

    def test_el_evento_no_se_publica_al_confirmar(self) -> None:
        """Publicar es del relay: el caso de uso solo encola."""

        billetera = self._billetera_de(f"prov-{uuid4()}")

        self._acreditar(str(billetera.id))

        self.assertEqual(self.broker.publicados, ())

    def test_un_fallo_antes_de_confirmar_no_deja_ni_saldo_ni_evento(self) -> None:
        """La razón de ser del patrón: los dos viajan en el mismo commit."""

        billetera = self._billetera_de(f"prov-{uuid4()}", saldo="100000.00")

        with self.assertRaises(RuntimeError):
            with self._crear_uow() as uow:
                guardada = uow.billeteras.obtener_por_id(billetera.id)
                guardada.acreditar(
                    Dinero(Decimal("50000.00"), "COP"), MotivoMovimiento.AJUSTE_MANUAL, "ajuste"
                )
                uow.billeteras.guardar(guardada)
                from app.aplicacion.eventos import encolar_eventos_pendientes

                encolar_eventos_pendientes(guardada, uow)
                raise RuntimeError("Fallo simulado antes de confirmar")

        self.assertEqual(self._eventos(), [], "el anuncio no sobrevive a la reversión")
        with self.SessionTest() as sesion:
            movimientos = sesion.scalars(
                select(MovimientoModel).where(MovimientoModel.billetera_id == billetera.id.valor)
            ).all()
        self.assertEqual(len(movimientos), 1, "el saldo tampoco se movió")

    def test_el_rechazo_se_encola_aunque_su_transaccion_se_revierta(self) -> None:
        """El retiro sin fondos no mueve el saldo, pero el hecho sí debe salir."""

        proveedor_id = f"prov-{uuid4()}"
        self._billetera_de(proveedor_id, saldo="10000.00")

        with self.assertRaises(FondosInsuficientesError):
            RetirarSaldoProveedorHandler(self._crear_uow(), self.dispatcher).ejecutar(
                RetirarSaldoProveedorCommand(proveedor_id, Decimal("99000.00"))
            )

        tipos = [evento.tipo for evento in self._eventos("PENDIENTE")]
        self.assertEqual(tipos, ["DebitoRechazadoV1"])


class TestRelay(BaseOutboxTest):
    """La otra mitad: publicar lo confirmado, reintentando lo que falle."""

    def test_publica_lo_pendiente_y_lo_marca(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))

        resultado = self._relay().publicar_pendientes()

        self.assertEqual(resultado.publicados, 1)
        self.assertEqual(len(self.broker.publicados), 1)
        sobre = self.broker.publicados[0]
        self.assertEqual(sobre.tipo, "SaldoAcreditadoV1")
        self.assertEqual(sobre.payload["monto"], "80000.00")
        publicados = self._eventos("PUBLICADO")
        self.assertEqual(len(publicados), 1)
        self.assertIsNotNone(publicados[0].fecha_publicacion)
        self.assertEqual(self._eventos("PENDIENTE"), [])

    def test_no_publica_dos_veces_el_mismo_evento(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))
        relay = self._relay()

        relay.publicar_pendientes()
        segundo = relay.publicar_pendientes()

        self.assertEqual(segundo.publicados, 0)
        self.assertEqual(len(self.broker.publicados), 1)

    def test_broker_caido_conserva_el_evento_y_espera(self) -> None:
        """Lo que el patrón promete: con el broker caído no se pierde, se acumula."""

        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))
        self.broker.fallar = True

        resultado = self._relay(espera_base=60.0).publicar_pendientes()

        self.assertEqual(resultado.fallidos, 1)
        self.assertEqual(self.broker.publicados, ())
        pendiente = self._eventos("PENDIENTE")[0]
        self.assertEqual(pendiente.intentos, 1)
        self.assertIn("broker no disponible", pendiente.error)

    def test_el_backoff_aplaza_el_siguiente_intento(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))
        self.broker.fallar = True
        relay = self._relay(espera_base=60.0)

        relay.publicar_pendientes()
        self.broker.fallar = False
        segundo = relay.publicar_pendientes()

        self.assertEqual(
            segundo.publicados, 0, "el evento sigue esperando: aún no vence su backoff"
        )
        self.assertEqual(self._eventos("PENDIENTE")[0].intentos, 1)

    def test_cuando_el_broker_vuelve_sale_lo_acumulado(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self.broker.fallar = True
        relay = self._relay(espera_base=0.0)
        for numero in range(3):
            self._acreditar(str(billetera.id), referencia=f"trabajo-{numero}")
            relay.publicar_pendientes()

        self.assertEqual(len(self._eventos("PENDIENTE")), 3)

        self.broker.fallar = False
        resultado = relay.publicar_pendientes()

        self.assertEqual(resultado.publicados, 3)
        self.assertEqual(len(self.broker.publicados), 3)
        self.assertEqual(self._eventos("PENDIENTE"), [])

    def test_un_fallo_detiene_el_lote_sin_perder_el_resto(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        for numero in range(3):
            self._acreditar(str(billetera.id), referencia=f"trabajo-{numero}")
        self.broker.fallar = True

        self._relay(espera_base=60.0).publicar_pendientes()

        self.assertEqual(len(self._eventos("PENDIENTE")), 3, "ninguno se dio por publicado")
        intentos = sorted(evento.intentos for evento in self._eventos("PENDIENTE"))
        self.assertEqual(intentos, [0, 0, 1], "solo el primero gastó un intento")

    def test_agotar_los_intentos_marca_fallido_y_se_puede_reencolar(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))
        self.broker.fallar = True
        relay = self._relay(max_intentos=2, espera_base=0.0)

        relay.publicar_pendientes()
        relay.publicar_pendientes()

        fallidos = self._eventos("FALLIDO")
        self.assertEqual(len(fallidos), 1)
        self.assertEqual(fallidos[0].intentos, 2)

        with self.SessionTest() as sesion:
            self.assertTrue(SqlAlchemyBandejaDeSalida(sesion).reencolar(fallidos[0].event_id))
            sesion.commit()

        self.broker.fallar = False
        self.assertEqual(relay.publicar_pendientes().publicados, 1)

    def test_no_toma_eventos_cuyo_backoff_sigue_vigente(self) -> None:
        billetera = self._billetera_de(f"prov-{uuid4()}")
        self._acreditar(str(billetera.id))
        with self.SessionTest() as sesion:
            fila = sesion.scalars(select(EventoSalienteModel)).one()
            fila.disponible_desde = datetime.now(timezone.utc) + timedelta(minutes=5)
            sesion.commit()

        self.assertEqual(self._relay().publicar_pendientes().publicados, 0)


class TestAcreditacionDeLaSagaConOutbox(BaseOutboxTest):
    """El paso 5 de la saga también pasa por la bandeja."""

    def _procesador(self) -> ProcesadorComandosSagaWallet:
        return ProcesadorComandosSagaWallet(
            fabrica_uow=self._crear_uow,
            dispatcher=self.dispatcher,
            politica=PoliticaDeReintentos(
                intentos=3, espera_inicial=0.01, factor=2.0, dormir=lambda _: None
            ),
        )

    def test_la_acreditacion_encola_su_evento(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        self._billetera_de(proveedor_id)

        resultado = self._procesador().acreditar_proveedor(
            saga_id=str(uuid4()),
            trabajo_id="trabajo-1",
            proveedor_id=proveedor_id,
            monto=Decimal("120000.00"),
            moneda="COP",
        )

        self.assertTrue(resultado.exitoso)
        self.assertEqual([e.tipo for e in self._eventos("PENDIENTE")], ["SaldoAcreditadoV1"])

    def test_el_comando_reentregado_no_encola_dos_veces(self) -> None:
        """La idempotencia del saldo debe cubrir también el anuncio."""

        proveedor_id = f"prov-{uuid4()}"
        self._billetera_de(proveedor_id)
        saga_id = str(uuid4())
        procesador = self._procesador()

        for _ in range(2):
            procesador.acreditar_proveedor(
                saga_id=saga_id,
                trabajo_id="trabajo-1",
                proveedor_id=proveedor_id,
                monto=Decimal("120000.00"),
                moneda="COP",
            )

        self.assertEqual(len(self._eventos()), 1)

    def test_la_acreditacion_rechazada_encola_su_rechazo(self) -> None:
        proveedor_id = f"prov-{uuid4()}"
        self._billetera_de(proveedor_id, suspendida=True)

        resultado = self._procesador().acreditar_proveedor(
            saga_id=str(uuid4()),
            trabajo_id="trabajo-1",
            proveedor_id=proveedor_id,
            monto=Decimal("120000.00"),
            moneda="COP",
        )

        self.assertFalse(resultado.exitoso)
        self.assertEqual(
            [e.tipo for e in self._eventos("PENDIENTE")], ["AcreditacionRechazadaV1"]
        )


class _ProductorFalso:
    def __init__(self, falla: bool = False) -> None:
        self.enviados: list[dict] = []
        self.cerrado = False
        self._falla = falla

    def send(self, datos, properties=None, partition_key=None):
        if self._falla:
            raise ConnectionError("pulsar no disponible")
        self.enviados.append(
            {"datos": datos, "properties": properties, "partition_key": partition_key}
        )

    def close(self) -> None:
        self.cerrado = True


class _ClienteFalso:
    def __init__(self, falla: bool = False) -> None:
        self.productor = _ProductorFalso(falla)
        self.cerrado = False

    def create_producer(self, topico, **_kwargs):
        self.topico = topico
        return self.productor

    def close(self) -> None:
        self.cerrado = True


class TestPulsarMessageBroker(unittest.TestCase):
    """El adaptador real, con un cliente falso: no necesita Pulsar levantado."""

    def _broker(self, falla: bool = False):
        clientes: list[_ClienteFalso] = []

        def fabrica(_url: str) -> _ClienteFalso:
            cliente = _ClienteFalso(falla)
            clientes.append(cliente)
            return cliente

        broker = PulsarMessageBroker(
            "pulsar://fake:6650", "persistent://public/default/pruebas",
            fabrica_de_cliente=fabrica,
        )
        return broker, clientes

    def _sobre(self) -> SobreDeEvento:
        return SobreDeEvento(
            tipo="SaldoAcreditadoV1",
            event_id=uuid4(),
            clave_particion="bil-1",
            payload={"billetera_id": "bil-1", "monto": "1000.00"},
        )

    def test_publica_con_tipo_y_clave_de_particion_en_el_sobre(self) -> None:
        broker, clientes = self._broker()
        sobre = self._sobre()

        broker.publicar(sobre)

        enviado = clientes[0].productor.enviados[0]
        self.assertEqual(enviado["partition_key"], "bil-1")
        self.assertEqual(enviado["properties"]["event_type"], "SaldoAcreditadoV1")
        self.assertEqual(enviado["properties"]["event_id"], str(sobre.event_id))
        self.assertIn(b"1000.00", enviado["datos"])

    def test_reutiliza_el_productor_entre_envios(self) -> None:
        broker, clientes = self._broker()

        broker.publicar(self._sobre())
        broker.publicar(self._sobre())

        self.assertEqual(len(clientes), 1, "no debe abrir una conexión por evento")
        self.assertEqual(len(clientes[0].productor.enviados), 2)

    def test_un_envio_fallido_propaga_y_descarta_la_conexion(self) -> None:
        """El relay necesita la excepción para reintentar, y una conexión limpia."""

        broker, clientes = self._broker(falla=True)

        with self.assertRaises(ConnectionError):
            broker.publicar(self._sobre())

        self.assertTrue(clientes[0].cerrado, "la conexión rota no se reutiliza")
        with self.assertRaises(ConnectionError):
            broker.publicar(self._sobre())
        self.assertEqual(len(clientes), 2, "el intento siguiente reconstruye la conexión")


if __name__ == "__main__":
    unittest.main()
