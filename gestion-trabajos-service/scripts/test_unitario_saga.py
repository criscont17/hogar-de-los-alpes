#!/usr/bin/env python3
"""Prueba unitaria del Orquestador de Saga y del Saga Log."""

import os
import sys
from decimal import Decimal
from uuid import uuid4

# Asegurar que el path del servicio esté disponible y usar SQLite para prueba unitaria
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["MESSAGE_BROKER"] = "memoria"


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.aplicacion.sagas.contratos_saga import SolicitudInicioSaga
from app.aplicacion.sagas.orquestador_saga_trabajo import OrquestadorSagaTrabajo
from app.dominio.trabajo.trabajo_repository import TrabajoRepository
from app.infraestructura.adaptadores.salida.persistencia.db import Base

from app.infraestructura.adaptadores.salida.persistencia.modelos_orm import TrabajoModel
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_saga_log_repository import (
    SqlAlchemySagaLogRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajo_repository import (
    SqlAlchemyTrabajoRepository,
)


class MockCommandPublisher:
    def __init__(self):
        self.comandos_enviados = []

    def enviar_comando(self, topico, tipo_comando, saga_id, payload, partition_key=None):
        self.comandos_enviados.append({
            "topico": topico,
            "tipo_comando": tipo_comando,
            "saga_id": saga_id,
            "payload": payload,
        })


def ejecutar_pruebas():
    print("\n--- Ejecutando Prueba Unitaria del Orquestador de Sagas y Saga Log ---")

    # Base de datos SQLite en memoria para la prueba
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    saga_log_repo = SqlAlchemySagaLogRepository(session_factory)
    publisher = MockCommandPublisher()

    # Repositorio de trabajo
    session = session_factory()
    trabajo_repo = SqlAlchemyTrabajoRepository(session)

    orquestador = OrquestadorSagaTrabajo(
        saga_log_repo=saga_log_repo,
        trabajo_repo=trabajo_repo,
        command_publisher=publisher,
        topico_comandos_pago="persistent://public/default/comandos-pago",
        topico_comandos_operaciones="persistent://public/default/comandos-operaciones",
    )

    # 1. TEST: Camino Feliz (Happy Path)
    print("\n1. Probando Camino Feliz (Happy Path)...")
    trabajo_id = uuid4()
    solicitud = SolicitudInicioSaga(
        trabajo_id=trabajo_id,
        cliente_id="cliente-1",
        descripcion="Pintura de fachada",
        pais="CO",
        ciudad="Bogotá",
        direccion="Calle 10 # 5-20",
        moneda="COP",
        monto_estimado=Decimal("250000.00"),
        partner_id="banco-bogota",
        referencia_externa="REF-BOG-001",
    )

    saga_id = orquestador.iniciar_saga(solicitud)
    assert len(publisher.comandos_enviados) == 1
    assert publisher.comandos_enviados[0]["tipo_comando"] == "AutorizarPagoTrabajoV1"
    print("   ✓ Paso 1 (Crear Trabajo) completado y Paso 2 (AutorizarPago) emitido a PagosBC")

    # Simular respuesta de PagosBC
    orquestador.procesar_pago_autorizado(saga_id, {"estado": "AUTORIZADO", "monto": 250000.0})
    assert len(publisher.comandos_enviados) == 2
    assert publisher.comandos_enviados[1]["tipo_comando"] == "AsignarProveedorTrabajoV1"
    print("   ✓ Paso 2 completado en Saga Log y Paso 3 (AsignarProveedor) emitido a OperacionesBC")

    # Simular respuesta de OperacionesBC
    orquestador.procesar_proveedor_asignado(saga_id, {"proveedor_id": "prov-01", "estado": "ASIGNADO"})
    instancia_saga = saga_log_repo.obtener_saga(saga_id)
    assert instancia_saga.estado_global == "COMPLETADA_EXITOSA"
    assert len(instancia_saga.pasos) == 3
    print("   ✓ Saga completada exitosamente. Estado global = COMPLETADA_EXITOSA")

    # 2. TEST: Camino con Fallo y Compensación (Fallo en Asignación de Proveedor)
    print("\n2. Probando Camino con Fallo y Compensación (Fallo en OperacionesBC)...")
    publisher.comandos_enviados.clear()
    trabajo_id_fallo = uuid4()
    solicitud_fallo = SolicitudInicioSaga(
        trabajo_id=trabajo_id_fallo,
        cliente_id="cliente-2",
        descripcion="Instalación de cerradura",
        pais="CO",
        ciudad="Medellín",
        direccion="Carrera 43A # 1-50",
        moneda="COP",
        monto_estimado=Decimal("120000.00"),
    )

    saga_fallo_id = orquestador.iniciar_saga(solicitud_fallo)
    # Pagos autoriza
    orquestador.procesar_pago_autorizado(saga_fallo_id, {"estado": "AUTORIZADO"})
    
    # Operaciones rechaza (ej. sin cobertura)
    orquestador.procesar_proveedor_rechazado(
        saga_fallo_id, {"motivo": "Sin proveedores con cobertura en la zona"}
    )

    # Verificar compensación
    # Debe haber emitido comando RevertirPagoTrabajoV1 hacia PagosBC
    comandos_compensacion = [c for c in publisher.comandos_enviados if c["tipo_comando"] == "RevertirPagoTrabajoV1"]
    assert len(comandos_compensacion) == 1
    print("   ✓ Comando de compensación RevertirPagoTrabajoV1 emitido a PagosBC")

    instancia_fallo = saga_log_repo.obtener_saga(saga_fallo_id)
    assert instancia_fallo.estado_global == "COMPENSANDO"
    print("   ✓ Saga queda COMPENSANDO hasta recibir la confirmación de PagosBC")

    # Pagos confirma el reverso de su autorización antes de que el orquestador
    # cancele el trabajo y declare consistencia eventual.
    orquestador.procesar_pago_revertido(saga_fallo_id, {"revertido": True})
    instancia_fallo = saga_log_repo.obtener_saga(saga_fallo_id)
    assert instancia_fallo.estado_global == "COMPENSADA"
    paso_reverso = next(p for p in instancia_fallo.pasos if p.nombre_paso == "COMPENSAR_REVERTIR_PAGO")
    assert paso_reverso.estado_paso == "COMPENSADO"
    print("   ✓ Saga Log registra el reverso y el estado final = COMPENSADA")

    # Verificar que el trabajo preliminar quedó CANCELADO
    from app.dominio.trabajo import TrabajoId
    trabajo_cancelado = trabajo_repo.obtener_por_id(TrabajoId(instancia_fallo.trabajo_id))
    assert trabajo_cancelado.estado.value == "Cancelado"
    print("   ✓ Trabajo preliminar en GestionDeTrabajosBC compensado y transicionado a CANCELADO")



    print("\n========================================================")
    print("  ¡TODAS LAS PRUEBAS DE LA SAGA Y SAGA LOG PASARON CON ÉXITO!")
    print("========================================================\n")


if __name__ == "__main__":
    ejecutar_pruebas()
