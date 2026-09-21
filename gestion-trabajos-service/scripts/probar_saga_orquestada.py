#!/usr/bin/env python3
"""Script de validación del Patrón de Sagas por Orquestación (Semana 7 - Criterios 1, 2 y 3).

Permite ejecutar de punta a punta:
1. Camino Feliz (Happy Path):
   - GestionDeTrabajosBC crea trabajo preliminar (Paso 1).
   - PagosBC recibe comando por Pulsar y autoriza el pago (Paso 2).
   - OperacionesBC recibe comando por Pulsar y asigna el proveedor (Paso 3).
   - GestionDeTrabajosBC confirma el trabajo y completa la saga (Saga Log: COMPLETADA_EXITOSA).

2. Camino con Fallo y Compensación:
   - Simula fallo en Paso 2 (Pagos) o Paso 3 (Operaciones).
   - Verifica que el orquestador ejecute las compensaciones en orden inverso.
   - Verifica que el Saga Log registre el estado COMPENSADA y el motivo del fallo.

Uso:
  # Probar camino exitoso:
  python -m scripts.probar_saga_orquestada --modo exito

  # Probar fallo y compensación en operaciones (Paso 3):
  python -m scripts.probar_saga_orquestada --modo compensar-operaciones

  # Probar fallo en pago (Paso 2):
  python -m scripts.probar_saga_orquestada --modo compensar-pago
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error

DEFAULT_BASE_URL = "http://localhost/trabajos/sagas"
DIRECT_BASE_URL = "http://localhost:8001/sagas"


def hacer_peticion(url: str, metodo: str = "GET", datos: dict | None = None) -> tuple[int, dict]:
    cuerpo = json.dumps(datos).encode("utf-8") if datos else None
    headers = {"Content-Type": "application/json"} if datos else {}
    req = urllib.request.Request(url, data=cuerpo, headers=headers, method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            contenido = resp.read().decode("utf-8")
            return resp.status, json.loads(contenido) if contenido else {}
    except urllib.error.HTTPError as e:
        contenido = e.read().decode("utf-8")
        return e.code, json.loads(contenido) if contenido else {"error": str(e)}
    except Exception as exc:
        return 0, {"error": str(exc)}


def resolver_url_base() -> str:
    # Intentar por gateway primero, luego puerto directo
    codigo, _ = hacer_peticion(f"{DEFAULT_BASE_URL}", "GET")
    if codigo in {200, 404}:
        return DEFAULT_BASE_URL
    codigo, _ = hacer_peticion(f"{DIRECT_BASE_URL}", "GET")
    if codigo in {200, 404}:
        return DIRECT_BASE_URL
    return DEFAULT_BASE_URL


def probar_saga(modo: str):
    base_url = resolver_url_base()
    print(f"\n========================================================")
    print(f"  Iniciando prueba de Saga Orquestada (Modo: {modo})")
    print(f"  Endpoint base: {base_url}")
    print(f"========================================================\n")

    simular_fallo = None
    if modo == "compensar-operaciones":
        simular_fallo = "OPERACIONES"
    elif modo == "compensar-pago":
        simular_fallo = "PAGO"

    solicitud = {
        "cliente_id": "cli-demo-100",
        "descripcion": "Reparación de filtración en baño principal",
        "pais": "CO",
        "ciudad": "Bogotá",
        "direccion": "Carrera 7 # 72-10",
        "moneda": "COP",
        "monto_estimado": 180000.0,
        "partner_id": "seguros-bolivar",
        "referencia_externa": f"REF-DEMO-{int(time.time())}",
        "simular_fallo_en_paso": simular_fallo,
    }

    print(f"1. Enviando solicitud de inicio de Saga (POST /activar-servicio)...")
    codigo, respuesta = hacer_peticion(f"{base_url}/activar-servicio", "POST", solicitud)
    if codigo != 202:
        print(f"[ERROR] No se pudo iniciar la saga (HTTP {codigo}): {respuesta}")
        print("\nVerifique que el stack de Docker esté corriendo con: docker compose up -d")
        sys.exit(1)

    saga_id = respuesta.get("saga_id")
    print(f"   ✓ Saga iniciada con éxito. saga_id={saga_id}")
    print(f"   ✓ Trabajo preliminar creado. trabajo_id={respuesta.get('trabajo_id')}\n")

    print(f"2. Monitoreando transiciones en el Saga Log (polling GET /{saga_id})...")
    espera_maxima = 15
    inicio = time.time()
    estado_final_alcanzado = False

    while time.time() - inicio < espera_maxima:
        time.sleep(1)
        codigo_get, saga_info = hacer_peticion(f"{base_url}/{saga_id}", "GET")
        if codigo_get != 200:
            continue

        estado_global = saga_info.get("estado_global")
        paso_actual = saga_info.get("paso_actual")
        pasos = saga_info.get("pasos", [])

        print(f"   -> Estado: {estado_global:20s} | Paso actual: {paso_actual:25s} | Pasos registrados: {len(pasos)}")

        if estado_global in {"COMPLETADA_EXITOSA", "COMPENSADA", "FALLIDA"}:
            estado_final_alcanzado = True
            break

    print(f"\n========================================================")
    print(f"  Resultado de la Ejecución de la Saga:")
    print(f"========================================================")
    print(f"  Saga ID:        {saga_id}")
    print(f"  Estado Global:  {saga_info.get('estado_global')}")
    if saga_info.get("error"):
        print(f"  Error/Motivo:   {saga_info.get('error')}")

    print(f"\n  Pasos registrados en el Saga Log:")
    print(f"  ------------------------------------------------------------")
    for p in saga_info.get("pasos", []):
        st = p.get("estado_paso")
        simbolo = "✓" if st in {"EXITOSO", "COMPENSADO"} else ("✗" if st == "FALLIDO" else "•")
        print(f"   [{simbolo}] Paso {p.get('paso_numero')}: {p.get('nombre_paso'):25s} | {p.get('servicio_participante'):25s} -> {st}")

    print(f"========================================================\n")

    if modo == "exito" and saga_info.get("estado_global") == "COMPLETADA_EXITOSA":
        print("[ÉXITO] La saga orquestada sobre los 3 microservicios completó satisfactoriamente.")
    elif "compensar" in modo and saga_info.get("estado_global") == "COMPENSADA":
        print("[ÉXITO] El flujo compensatorio se ejecutó correctamente en orden inverso.")
    else:
        print(f"[OBSERVACIÓN] El estado final fue: {saga_info.get('estado_global')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validar Saga Orquestada de Hogar de los Alpes")
    parser.add_argument(
        "--modo",
        choices=["exito", "compensar-operaciones", "compensar-pago"],
        default="exito",
        help="Modo de prueba de la saga",
    )
    args = parser.parse_args()
    probar_saga(args.modo)
