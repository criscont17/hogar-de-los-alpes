#!/usr/bin/env python3
"""Prueba unitaria del Orquestador de Saga y del Saga Log.

Cubre los cinco pasos de la Saga de Activación de Servicio y sus tres desenlaces:

1. Camino feliz: crear trabajo → autorizar pago → asignar proveedor → ejecutar →
   acreditar wallet.
2. Compensación en orden inverso ante un rechazo (pago o asignación) y ante una
   ejecución fallida, que además libera la asignación ya realizada.
3. Política EN_DISPUTA: si la acreditación al proveedor falla de forma definitiva el
   trabajo NO se revierte, porque el servicio ya se prestó.
"""

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
from app.dominio.trabajo import TrabajoId
from app.infraestructura.adaptadores.salida.persistencia.db import Base

from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_saga_log_repository import (
    SqlAlchemySagaLogRepository,
)
from app.infraestructura.adaptadores.salida.persistencia.sqlalchemy_trabajo_repository import (
    SqlAlchemyTrabajoRepository,
)

TOPICO_PAGO = "persistent://public/default/comandos-pago"
TOPICO_OPERACIONES = "persistent://public/default/comandos-operaciones"
TOPICO_WALLET = "persistent://public/default/comandos-wallet"


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

    def tipos(self):
        return [c["tipo_comando"] for c in self.comandos_enviados]

    def ultimo(self, tipo_comando):
        for comando in reversed(self.comandos_enviados):
            if comando["tipo_comando"] == tipo_comando:
                return comando
        raise AssertionError(f"No se envió ningún comando {tipo_comando}")


class EspiaDeEventos:
    """Recoge los eventos de dominio que el orquestador anuncia tras cada cambio."""

    def __init__(self):
        self.recibidos = []

    def despachar(self, evento):
        self.recibidos.append(evento)

    def nombres(self):
        return [type(evento).__name__ for evento in self.recibidos]


def _solicitud(cliente_id, descripcion, simular_fallo=None, monto="250000.00"):
    return SolicitudInicioSaga(
        trabajo_id=uuid4(),
        cliente_id=cliente_id,
        descripcion=descripcion,
        pais="CO",
        ciudad="Bogotá",
        direccion="Calle 10 # 5-20",
        moneda="COP",
        monto_estimado=Decimal(monto),
        partner_id="banco-bogota",
        referencia_externa=f"REF-{uuid4()}",
        simular_fallo_en_paso=simular_fallo,
    )


def _nuevo_entorno():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    saga_log_repo = SqlAlchemySagaLogRepository(session_factory)
    publisher = MockCommandPublisher()
    espia = EspiaDeEventos()
    trabajo_repo = SqlAlchemyTrabajoRepository(session_factory())

    orquestador = OrquestadorSagaTrabajo(
        saga_log_repo=saga_log_repo,
        trabajo_repo=trabajo_repo,
        command_publisher=publisher,
        topico_comandos_pago=TOPICO_PAGO,
        topico_comandos_operaciones=TOPICO_OPERACIONES,
        topico_comandos_wallet=TOPICO_WALLET,
        dispatcher=espia,
    )
    return orquestador, saga_log_repo, trabajo_repo, publisher, espia


def probar_camino_feliz():
    print("\n1. Probando Camino Feliz (Happy Path, 5 pasos)...")
    orquestador, saga_log_repo, trabajo_repo, publisher, _ = _nuevo_entorno()

    saga_id = orquestador.iniciar_saga(_solicitud("cliente-1", "Pintura de fachada"))
    assert publisher.tipos() == ["AutorizarPagoTrabajoV1"]
    print("   ✓ Paso 1 (Crear Trabajo) completado y Paso 2 (AutorizarPago) emitido a PagosBC")

    orquestador.procesar_pago_autorizado(saga_id, {"estado": "AUTORIZADO", "monto": 250000.0})
    assert publisher.tipos()[-1] == "AsignarProveedorTrabajoV1"
    print("   ✓ Paso 2 completado en Saga Log y Paso 3 (AsignarProveedor) emitido a OperacionesBC")

    orquestador.procesar_proveedor_asignado(
        saga_id, {"proveedor_id": "prov-01", "estado": "ASIGNADO"}
    )
    assert "AcreditarProveedorV1" not in publisher.tipos(), (
        "no se acredita antes de que el trabajo se ejecute"
    )
    print("   ✓ Paso 3 completado y Paso 4 (EjecutarTrabajo) queda a la espera de OperacionesBC")

    orquestador.procesar_ejecucion_completada(saga_id, {"estado": "EJECUTADO"})
    comando_wallet = publisher.ultimo("AcreditarProveedorV1")
    assert comando_wallet["topico"] == TOPICO_WALLET
    assert comando_wallet["payload"]["proveedor_id"] == "prov-01"
    assert comando_wallet["payload"]["monto"] == 250000.0
    assert comando_wallet["payload"]["moneda"] == "COP"
    assert comando_wallet["payload"]["simular_fallo"] is False
    print("   ✓ Paso 4 completado y Paso 5 (AcreditarProveedor) emitido a WalletBC")

    orquestador.procesar_wallet_acreditada(
        saga_id, {"proveedor_id": "prov-01", "saldo_resultante": "250000.00", "intentos": 1}
    )
    instancia = saga_log_repo.obtener_saga(saga_id)
    assert instancia.estado_global == "COMPLETADA_EXITOSA", instancia.estado_global
    assert len(instancia.pasos) == 5
    assert all(paso.estado_paso == "EXITOSO" for paso in instancia.pasos)
    print("   ✓ Saga completada exitosamente sobre 4 microservicios. Estado = COMPLETADA_EXITOSA")

    trabajo = trabajo_repo.obtener_por_id(TrabajoId(instancia.trabajo_id))
    assert trabajo.estado.value == "Creado"
    print("   ✓ El trabajo no quedó cancelado ni en disputa")


def probar_compensacion_por_asignacion():
    print("\n2. Probando Compensación por fallo en OperacionesBC (Paso 3)...")
    orquestador, saga_log_repo, trabajo_repo, publisher, _ = _nuevo_entorno()

    saga_id = orquestador.iniciar_saga(_solicitud("cliente-2", "Instalación de cerradura"))
    orquestador.procesar_pago_autorizado(saga_id, {"estado": "AUTORIZADO"})
    orquestador.procesar_proveedor_rechazado(
        saga_id, {"motivo": "Sin proveedores con cobertura en la zona"}
    )

    assert publisher.tipos().count("RevertirPagoTrabajoV1") == 1
    assert "AcreditarProveedorV1" not in publisher.tipos(), (
        "no se acredita a nadie si la asignación se rechazó"
    )
    print("   ✓ Comando de compensación RevertirPagoTrabajoV1 emitido a PagosBC")

    instancia = saga_log_repo.obtener_saga(saga_id)
    assert instancia.estado_global == "COMPENSANDO"
    print("   ✓ Saga queda COMPENSANDO hasta recibir la confirmación de PagosBC")

    orquestador.procesar_pago_revertido(saga_id, {"revertido": True})
    instancia = saga_log_repo.obtener_saga(saga_id)
    assert instancia.estado_global == "COMPENSADA"
    paso_reverso = next(p for p in instancia.pasos if p.nombre_paso == "COMPENSAR_REVERTIR_PAGO")
    assert paso_reverso.estado_paso == "COMPENSADO"
    print("   ✓ Saga Log registra el reverso y el estado final = COMPENSADA")

    trabajo = trabajo_repo.obtener_por_id(TrabajoId(instancia.trabajo_id))
    assert trabajo.estado.value == "Cancelado"
    print("   ✓ Trabajo preliminar compensado y transicionado a CANCELADO")


def probar_compensacion_por_ejecucion_fallida():
    print("\n3. Probando Compensación por Ejecución Fallida (Paso 4: libera asignación y revierte pago)...")
    orquestador, saga_log_repo, trabajo_repo, publisher, _ = _nuevo_entorno()

    saga_id = orquestador.iniciar_saga(_solicitud("cliente-3", "Cambio de tubería"))
    orquestador.procesar_pago_autorizado(saga_id, {"estado": "AUTORIZADO"})
    orquestador.procesar_proveedor_asignado(saga_id, {"proveedor_id": "prov-02"})

    orquestador.procesar_ejecucion_fallida(
        saga_id, {"motivo": "El proveedor no pudo ejecutar el trabajo en sitio"}
    )
    assert "AcreditarProveedorV1" not in publisher.tipos(), (
        "un trabajo que no se ejecutó no se le paga a nadie"
    )
    assert publisher.tipos()[-1] == "LiberarAsignacionProveedorV1"
    print("   ✓ Primero se libera la asignación (compensación del Paso 3)")

    assert "RevertirPagoTrabajoV1" not in publisher.tipos(), (
        "el pago no se revierte antes de confirmar la liberación"
    )

    orquestador.procesar_asignacion_liberada(saga_id, {"liberado": True})
    assert publisher.tipos()[-1] == "RevertirPagoTrabajoV1"
    print("   ✓ Confirmada la liberación, se revierte el pago (compensación del Paso 2)")

    orquestador.procesar_pago_revertido(saga_id, {"revertido": True})
    instancia = saga_log_repo.obtener_saga(saga_id)
    assert instancia.estado_global == "COMPENSADA"

    # El orden inverso se comprueba en la secuencia de comandos emitidos: el Saga Log
    # devuelve sus pasos ordenados por número de paso, no cronológicamente.
    assert publisher.tipos() == [
        "AutorizarPagoTrabajoV1",
        "AsignarProveedorTrabajoV1",
        "LiberarAsignacionProveedorV1",
        "RevertirPagoTrabajoV1",
    ]
    compensaciones = {
        p.nombre_paso: p.estado_paso for p in instancia.pasos if p.nombre_paso.startswith("COMPENSAR")
    }
    assert compensaciones == {
        "COMPENSAR_LIBERAR_ASIGNACION": "COMPENSADO",
        "COMPENSAR_REVERTIR_PAGO": "COMPENSADO",
        "COMPENSAR_CREAR_TRABAJO": "COMPENSADO",
    }, compensaciones
    print("   ✓ Las tres compensaciones se ejecutaron y quedaron registradas en orden inverso")

    trabajo = trabajo_repo.obtener_por_id(TrabajoId(instancia.trabajo_id))
    assert trabajo.estado.value == "Cancelado"
    print("   ✓ Trabajo transicionado a CANCELADO")


def probar_disputa_por_acreditacion_fallida():
    print("\n4. Probando política EN_DISPUTA (Paso 5 fallido, sin reverso)...")
    orquestador, saga_log_repo, trabajo_repo, publisher, espia = _nuevo_entorno()

    saga_id = orquestador.iniciar_saga(
        _solicitud("cliente-4", "Reparación eléctrica", simular_fallo="WALLET")
    )
    orquestador.procesar_pago_autorizado(saga_id, {"estado": "AUTORIZADO"})
    orquestador.procesar_proveedor_asignado(saga_id, {"proveedor_id": "prov-03"})
    orquestador.procesar_ejecucion_completada(saga_id, {"estado": "EJECUTADO"})

    comando_wallet = publisher.ultimo("AcreditarProveedorV1")
    assert comando_wallet["payload"]["simular_fallo"] is True
    print("   ✓ El fallo simulado viaja en el comando hacia WalletBC")

    orquestador.procesar_acreditacion_fallida(
        saga_id,
        {
            "motivo": "Billetera bloqueada por la pasarela interna",
            "intentos": 3,
            "requiere_revision_manual": True,
        },
    )

    instancia = saga_log_repo.obtener_saga(saga_id)
    assert instancia.estado_global == "EN_DISPUTA", instancia.estado_global
    print("   ✓ Saga Log finaliza en EN_DISPUTA con el motivo del fallo")

    assert "RevertirPagoTrabajoV1" not in publisher.tipos(), (
        "el pago NO se revierte: el trabajo físico ya se ejecutó"
    )
    assert "LiberarAsignacionProveedorV1" not in publisher.tipos(), (
        "la asignación NO se libera: el proveedor sí hizo el trabajo"
    )
    print("   ✓ No se emitió ninguna compensación")

    trabajo = trabajo_repo.obtener_por_id(TrabajoId(instancia.trabajo_id))
    assert trabajo.estado.value == "EnDisputa", trabajo.estado.value
    print("   ✓ El trabajo quedó EN_DISPUTA para revisión manual de Operaciones")

    assert "TrabajoEnDisputa" in espia.nombres()
    print("   ✓ Se anunció TrabajoEnDisputa para que Operaciones lo vea en su bandeja")

    paso_disputa = next(
        p for p in instancia.pasos if p.nombre_paso == "ABRIR_DISPUTA_REVISION_MANUAL"
    )
    assert paso_disputa.evento_recibido["requiere_revision_manual"] is True
    assert paso_disputa.evento_recibido["intentos_de_acreditacion"] == 3
    print("   ✓ El Saga Log deja trazabilidad de los intentos y de la revisión pendiente")


def ejecutar_pruebas():
    print("\n--- Ejecutando Prueba Unitaria del Orquestador de Sagas y Saga Log ---")
    probar_camino_feliz()
    probar_compensacion_por_asignacion()
    probar_compensacion_por_ejecucion_fallida()
    probar_disputa_por_acreditacion_fallida()

    print("\n========================================================")
    print("  ¡TODAS LAS PRUEBAS DE LA SAGA Y SAGA LOG PASARON CON ÉXITO!")
    print("========================================================\n")


if __name__ == "__main__":
    ejecutar_pruebas()
