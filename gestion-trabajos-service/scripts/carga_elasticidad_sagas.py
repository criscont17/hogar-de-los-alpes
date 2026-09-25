"""Escenario de calidad — Elasticidad: pico de demanda de activación de servicios.

Simula un evento climático: durante unos minutos llegan muchas más solicitudes de
servicio que en un día normal. El experimento sube el ritmo de inicio de sagas por
etapas hasta `4x` la línea base y mide dos latencias distintas, que conviene no
confundir:

- **Aceptación (HTTP):** lo que tarda `POST /sagas/activar-servicio` en responder
  `202`. Es lo que percibe el partner que envía la solicitud. Dentro de esa
  petición solo ocurren el paso 1 (crear el trabajo preliminar) y la publicación
  del comando de pago; el resto de la saga es asíncrono.
- **Extremo a extremo (saga):** lo que tarda la transacción distribuida completa,
  medido con las marcas de tiempo del propio Saga Log
  (`fecha_actualizacion - fecha_creacion`), así que no incluye el sondeo del
  script ni el ida y vuelta HTTP.

La *tasa de saturación* es la fracción de sagas que, agotado el periodo de
drenaje, siguen en un estado no final: el sistema aceptó la solicitud pero no
alcanzó a completar la transacción. Es la métrica que delata el punto de quiebre.

Uso (con el stack arriba, desde `gestion-trabajos-service/`):

    python -m scripts.carga_elasticidad_sagas                      # 1x→4x sobre 2 sagas/s
    python -m scripts.carga_elasticidad_sagas --base 5 --duracion 30
    python -m scripts.carga_elasticidad_sagas --multiplicadores 1,4 --csv

Para el experimento con dos réplicas del orquestador, levante primero
`docker compose --profile escalabilidad up -d --build gestion-trabajos-2` y
vuelva a correr el mismo comando: ambas comparten la suscripción `Shared`.
"""

from __future__ import annotations

import argparse
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from scripts.comun_experimentos import (
    Endpoints,
    consultar_saga,
    duracion_segundos,
    es_final,
    escribir_csv,
    fila_metrica,
    iniciar_saga,
    marca_de_tiempo,
    pedir,
    percentil,
    resolver_endpoints_o_salir,
    titulo,
    veredicto,
)

# Metas del escenario. La aceptación tiene que seguir siendo interactiva incluso
# en el pico; la saga completa puede tardar más porque cruza cuatro servicios.
META_ACEPTACION_P95_MS = 500.0
META_ACEPTACION_P99_MS = 1000.0
META_SATURACION = 0.01


@dataclass
class Muestra:
    etapa: int
    multiplicador: int
    objetivo_por_segundo: float
    saga_id: str | None
    codigo: int
    latencia_ms: float
    t_inicio: float
    t_fin: float
    detalle: str = ""

    @property
    def aceptada(self) -> bool:
        return self.codigo == 202


def _lanzar_una(
    endpoints: Endpoints,
    etapa: int,
    multiplicador: int,
    objetivo: float,
    monto: float,
    indice: int,
) -> Muestra:
    t_inicio = time.perf_counter()
    respuesta = iniciar_saga(
        endpoints,
        monto=monto,
        cliente_id=f"cli-elasticidad-{etapa}-{indice}",
        referencia_externa=f"ELAST-{etapa}-{indice}-{uuid.uuid4().hex[:8]}",
        descripcion="Siniestro sintético del experimento de elasticidad",
    )
    t_fin = time.perf_counter()

    saga_id = None
    detalle = ""
    if respuesta.codigo == 202 and isinstance(respuesta.cuerpo, dict):
        saga_id = respuesta.cuerpo.get("saga_id")
    else:
        detalle = str(respuesta.cuerpo)[:160]

    return Muestra(
        etapa=etapa,
        multiplicador=multiplicador,
        objetivo_por_segundo=objetivo,
        saga_id=saga_id,
        codigo=respuesta.codigo,
        latencia_ms=respuesta.latencia_ms,
        t_inicio=t_inicio,
        t_fin=t_fin,
        detalle=detalle,
    )


def _emitir_etapa(
    endpoints: Endpoints,
    *,
    etapa: int,
    multiplicador: int,
    objetivo: float,
    duracion: float,
    monto_base: float,
    hilos: int,
) -> list[Muestra]:
    """Emite solicitudes a ritmo constante durante `duracion` segundos.

    El ritmo lo marca el hilo principal y el trabajo lo hacen los hilos del pool:
    si el sistema se satura, la cola del pool crece y eso aparece como latencia de
    aceptación más alta, no como un ritmo de emisión más bajo. Así se distingue
    "el cliente envió menos" de "el sistema respondió más lento".
    """

    total = max(int(round(objetivo * duracion)), 1)
    intervalo = 1.0 / objetivo
    print(
        f"  Etapa {etapa} ({multiplicador}x): {objetivo:.1f} sagas/s objetivo · "
        f"{total} solicitudes en ~{duracion:.0f}s"
    )

    futuros = []
    referencia = time.perf_counter()
    with ThreadPoolExecutor(max_workers=hilos, thread_name_prefix=f"elast-{etapa}") as pool:
        for indice in range(total):
            espera = (referencia + indice * intervalo) - time.perf_counter()
            if espera > 0:
                time.sleep(espera)
            futuros.append(
                pool.submit(
                    _lanzar_una,
                    endpoints,
                    etapa,
                    multiplicador,
                    objetivo,
                    monto_base + indice,
                    indice,
                )
            )

    muestras = [futuro.result() for futuro in futuros]
    aceptadas = sum(1 for m in muestras if m.aceptada)
    print(f"     aceptadas {aceptadas}/{total}")
    return muestras


def _calentar(endpoints: Endpoints, monto: float) -> None:
    """Corre una saga sola y espera a que cierre.

    La primera saga de un Pulsar recién arrancado paga la creación de los seis
    tópicos y sus suscripciones. Cobrarle eso a la etapa 1 falsearía la línea base.
    """

    print("  Calentando (una saga completa para crear tópicos y suscripciones)…")
    respuesta = iniciar_saga(
        endpoints,
        monto=monto,
        cliente_id="cli-elasticidad-calentamiento",
        referencia_externa=f"ELAST-WARMUP-{uuid.uuid4().hex[:8]}",
    )
    if respuesta.codigo != 202 or not isinstance(respuesta.cuerpo, dict):
        raise RuntimeError(f"El calentamiento falló (HTTP {respuesta.codigo}): {respuesta.cuerpo}")

    saga_id = respuesta.cuerpo["saga_id"]
    limite = time.perf_counter() + 90
    while time.perf_counter() < limite:
        time.sleep(1.5)
        estado = consultar_saga(endpoints, saga_id).get("estado_global")
        if es_final(estado):
            print(f"     saga de calentamiento: {estado}")
            return
    print("     [aviso] la saga de calentamiento no cerró en 90s; el stack puede estar frío")


def _estados_globales(endpoints: Endpoints, limite: int) -> dict[str, str]:
    """Un solo `GET /sagas` para todos los estados: sondear una por una sería carga."""

    respuesta = pedir(f"{endpoints.sagas}?limite={limite}")
    if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
        return {}
    return {i["saga_id"]: i.get("estado_global", "") for i in respuesta.cuerpo}


def _drenar(
    endpoints: Endpoints, saga_ids: list[str], segundos: float, intervalo: float = 3.0
) -> set[str]:
    """Espera a que las sagas aceptadas cierren. Devuelve las que quedaron abiertas."""

    print()
    print(f"  Drenando hasta {segundos:.0f}s para que las sagas en vuelo cierren…")
    pendientes = set(saga_ids)
    limite_consulta = len(saga_ids) + 50
    limite = time.perf_counter() + segundos

    while pendientes and time.perf_counter() < limite:
        time.sleep(intervalo)
        estados = _estados_globales(endpoints, limite_consulta)
        antes = len(pendientes)
        pendientes = {s for s in pendientes if not es_final(estados.get(s))}
        if len(pendientes) != antes:
            print(f"     cerradas {len(saga_ids) - len(pendientes)}/{len(saga_ids)}")

    if pendientes:
        print(f"     quedaron {len(pendientes)} sagas sin estado final")
    return pendientes


def _barrer_detalle(endpoints: Endpoints, saga_ids: list[str], hilos: int) -> dict[str, dict]:
    """Lee el Saga Log completo de cada saga para sacar su duración real."""

    with ThreadPoolExecutor(max_workers=min(hilos, 12)) as pool:
        resultados = pool.map(lambda s: (s, consultar_saga(endpoints, s)), saga_ids)
    return dict(resultados)


def _reportar_etapa(muestras: list[Muestra], detalles: dict[str, dict]) -> dict[str, float]:
    total = len(muestras)
    aceptadas = [m for m in muestras if m.aceptada]
    latencias = [m.latencia_ms for m in muestras]

    objetivo = muestras[0].objetivo_por_segundo
    # La etapa dura `n / objetivo` por construcción del emisor: la última solicitud
    # arranca un intervalo antes de que termine, no en el instante final. Tomar solo
    # la ventana observada haría parecer que el ritmo logrado supera al objetivo.
    # Si el sistema se satura y las respuestas se arrastran, la ventana observada es
    # mayor y es la que manda.
    observada = max(m.t_fin for m in muestras) - min(m.t_inicio for m in muestras)
    ventana = max(observada, len(muestras) / objetivo, 1e-6)

    sagas = [detalles.get(m.saga_id, {}) for m in aceptadas if m.saga_id]
    finales = [s for s in sagas if es_final(s.get("estado_global"))]
    duraciones = [d for d in (duracion_segundos(s) for s in finales) if d is not None]
    saturadas = len(sagas) - len(finales)

    estados: dict[str, int] = {}
    for saga in sagas:
        estado = saga.get("estado_global", "SIN_RESPUESTA")
        estados[estado] = estados.get(estado, 0) + 1

    print()
    print(f"  --- Etapa {muestras[0].etapa} — {muestras[0].multiplicador}x la línea base ---")
    fila_metrica("Ritmo objetivo (sagas/s)", f"{objetivo:.2f}")
    fila_metrica("Ritmo logrado (sagas/s)", f"{len(aceptadas) / ventana:.2f}")
    fila_metrica("Throughput de peticiones (req/s)", f"{total / ventana:.2f}")
    fila_metrica("Aceptadas (202)", f"{len(aceptadas)}/{total} ({len(aceptadas) / total:.1%})")
    fila_metrica("Aceptación — promedio", f"{statistics.fmean(latencias):.1f} ms")
    fila_metrica("Aceptación — p50", f"{percentil(latencias, 50):.1f} ms")
    fila_metrica("Aceptación — p95", f"{percentil(latencias, 95):.1f} ms", "< 500 ms")
    fila_metrica("Aceptación — p99", f"{percentil(latencias, 99):.1f} ms", "< 1000 ms")
    if duraciones:
        fila_metrica("Saga completa — p50", f"{percentil(duraciones, 50):.2f} s")
        fila_metrica("Saga completa — p95", f"{percentil(duraciones, 95):.2f} s")
        fila_metrica("Saga completa — p99", f"{percentil(duraciones, 99):.2f} s")
    tasa_saturacion = saturadas / len(sagas) if sagas else 0.0
    fila_metrica("Sagas en saturación", f"{saturadas}/{len(sagas)} ({tasa_saturacion:.1%})", "< 1%")
    fila_metrica("Desenlaces", ", ".join(f"{k}={v}" for k, v in sorted(estados.items())) or "—")

    fallidas = [m for m in muestras if not m.aceptada]
    if fallidas:
        primera = fallidas[0]
        fila_metrica("Rechazos de aceptación", f"{len(fallidas)} (ej. HTTP {primera.codigo})")
        print(f"      └─ {primera.detalle}")

    return {
        "objetivo": objetivo,
        "logrado": len(aceptadas) / ventana,
        "req_s": total / ventana,
        "p95_aceptacion": percentil(latencias, 95),
        "p99_aceptacion": percentil(latencias, 99),
        "p95_saga": percentil(duraciones, 95) if duraciones else 0.0,
        "saturacion": tasa_saturacion,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", type=float, default=2.0, help="Línea base en sagas/segundo")
    parser.add_argument(
        "--multiplicadores",
        default="1,2,3,4",
        help="Multiplicadores de la línea base, separados por coma",
    )
    parser.add_argument("--duracion", type=float, default=20.0, help="Segundos por etapa")
    parser.add_argument("--drenaje", type=float, default=90.0, help="Segundos máximos de drenaje")
    parser.add_argument("--hilos", type=int, default=16, help="Hilos emisores por etapa")
    parser.add_argument("--monto-base", type=float, default=150000.0, help="Monto de cada saga")
    parser.add_argument("--via", choices=["auto", "gateway", "directo"], default="auto")
    parser.add_argument("--sin-calentamiento", action="store_true")
    parser.add_argument("--csv", action="store_true", help="Escribe el detalle por saga en CSV")
    args = parser.parse_args()

    multiplicadores = [int(m) for m in args.multiplicadores.split(",") if m.strip()]
    endpoints = resolver_endpoints_o_salir(args.via)

    titulo("Escenario de calidad — Elasticidad ante picos de demanda")
    fila_metrica("Entrada usada", f"{endpoints.trabajos} ({endpoints.via})")
    fila_metrica("Línea base", f"{args.base:.1f} sagas/s")
    fila_metrica("Rampa", " → ".join(f"{m}x" for m in multiplicadores))
    fila_metrica(
        "Solicitudes previstas",
        sum(int(round(args.base * m * args.duracion)) for m in multiplicadores),
    )
    print()

    if not args.sin_calentamiento:
        _calentar(endpoints, args.monto_base)

    print()
    print("  Ejecutando la rampa (sin pausas entre etapas, como un pico real):")
    muestras_por_etapa: list[list[Muestra]] = []
    for etapa, multiplicador in enumerate(multiplicadores, start=1):
        muestras_por_etapa.append(
            _emitir_etapa(
                endpoints,
                etapa=etapa,
                multiplicador=multiplicador,
                objetivo=args.base * multiplicador,
                duracion=args.duracion,
                monto_base=args.monto_base,
                hilos=args.hilos,
            )
        )

    todas = [m for etapa in muestras_por_etapa for m in etapa]
    ids_aceptados = [m.saga_id for m in todas if m.saga_id]
    if not ids_aceptados:
        print("\n  Ninguna saga fue aceptada; revise los logs de gestion-trabajos.")
        raise SystemExit(1)

    _drenar(endpoints, ids_aceptados, args.drenaje)
    detalles = _barrer_detalle(endpoints, ids_aceptados, args.hilos)

    titulo("Resultados por etapa")
    resumenes = [_reportar_etapa(muestras, detalles) for muestras in muestras_por_etapa]

    pico = resumenes[-1]
    base = resumenes[0]
    titulo("Veredicto del escenario")
    fila_metrica("Sagas iniciadas en total", len(ids_aceptados))
    fila_metrica(
        "Ritmo en el pico",
        f"{pico['logrado']:.2f} sagas/s de {pico['objetivo']:.2f} objetivo "
        f"({pico['logrado'] / pico['objetivo']:.0%} del objetivo)",
    )
    if base["p95_aceptacion"] > 0:
        fila_metrica(
            "Degradación de aceptación p95 (1x→pico)",
            f"{base['p95_aceptacion']:.0f} ms → {pico['p95_aceptacion']:.0f} ms "
            f"(x{pico['p95_aceptacion'] / base['p95_aceptacion']:.1f})",
        )
    if base["p95_saga"] > 0 and pico["p95_saga"] > 0:
        fila_metrica(
            "Degradación de la saga p95 (1x→pico)",
            f"{base['p95_saga']:.1f} s → {pico['p95_saga']:.1f} s "
            f"(x{pico['p95_saga'] / base['p95_saga']:.1f})",
        )
    print()
    veredicto(
        f"Aceptación p95 < {META_ACEPTACION_P95_MS:.0f} ms en el pico",
        pico["p95_aceptacion"] < META_ACEPTACION_P95_MS,
    )
    veredicto(
        f"Aceptación p99 < {META_ACEPTACION_P99_MS:.0f} ms en el pico",
        pico["p99_aceptacion"] < META_ACEPTACION_P99_MS,
    )
    veredicto(
        f"Saturación < {META_SATURACION:.0%} en el pico", pico["saturacion"] < META_SATURACION
    )
    veredicto(
        "El ritmo logrado sigue al objetivo (>=90%)",
        pico["logrado"] >= pico["objetivo"] * 0.9,
    )

    if args.csv:
        ruta = Path.cwd() / f"elasticidad-{marca_de_tiempo()}.csv"
        filas = []
        for muestra in todas:
            saga = detalles.get(muestra.saga_id, {}) if muestra.saga_id else {}
            filas.append(
                [
                    muestra.etapa,
                    muestra.multiplicador,
                    f"{muestra.objetivo_por_segundo:.2f}",
                    muestra.saga_id or "",
                    muestra.codigo,
                    f"{muestra.latencia_ms:.1f}",
                    saga.get("estado_global", ""),
                    f"{duracion_segundos(saga) or 0:.3f}",
                ]
            )
        escribir_csv(
            ruta,
            [
                "etapa",
                "multiplicador",
                "objetivo_sagas_s",
                "saga_id",
                "codigo_http",
                "aceptacion_ms",
                "estado_global",
                "duracion_saga_s",
            ],
            filas,
        )
        print()
        fila_metrica("Detalle por saga", ruta)


if __name__ == "__main__":
    main()
