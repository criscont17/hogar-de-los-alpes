"""Escenario de calidad — Consistencia transaccional bajo fallo concurrente.

Lanza sagas en paralelo forzando fallos aleatorios en los pasos posteriores a la
retención del pago y después audita el dinero cruzando tres fuentes que viven en
bases distintas:

- el **Saga Log** de GestionDeTrabajosBC (`GET /sagas/{id}`),
- el **pago** de PagosBC (`GET /pagos?trabajo_id=…`, referencia `saga:{id}:autorizacion`),
- el **movimiento** de WalletBC (`saga:{id}:acreditacion`).

La afirmación que se quiere poder sostener es que la discrepancia es
exactamente `0`: ni dinero fantasma (acreditado al proveedor sin haberse cobrado,
o acreditado dos veces) ni dinero perdido (cobrado al cliente y ni liquidado ni
revertido ni declarado en disputa). Se verifica con esta identidad contable:

    cobrado = acreditado + en custodia (sagas EN_DISPUTA)

`EN_DISPUTA` no es un descuadre: es custodia declarada. El servicio ya se prestó,
el cobro se sostiene y el Saga Log deja constancia de que Operaciones debe
resolverlo a mano. Lo que sí sería un descuadre es custodia sin saga que la
respalde.

Uso (con el stack arriba, desde `gestion-trabajos-service/`):

    python -m scripts.auditoria_consistencia_sagas --num 20
    python -m scripts.auditoria_consistencia_sagas --num 40 --pasos OPERACIONES,EJECUCION,WALLET
    python -m scripts.auditoria_consistencia_sagas --solo-auditar --limite 100 --csv

`--solo-auditar` no lanza nada: audita las sagas que ya estén en el log, que es lo
que conviene correr después del experimento de disponibilidad.

Termina con código de salida 1 si encuentra cualquier discrepancia.
"""

from __future__ import annotations

import argparse
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from scripts.comun_experimentos import (
    PROVEEDOR_DE_LA_SAGA,
    Endpoints,
    consultar_saga,
    es_final,
    escribir_csv,
    fila_metrica,
    iniciar_saga,
    marca_de_tiempo,
    paso_donde_quedo,
    pedir,
    resolver_endpoints_o_salir,
    titulo,
    veredicto,
)

# `NINGUNO` deja que la saga complete: sirve de control positivo frente a los
# fallos forzados. `PAGO` falla antes de retener el dinero, así que es el control
# negativo: no debería quedar rastro de plata en ninguna de las dos bases.
PASOS_DISPONIBLES = ("NINGUNO", "PAGO", "OPERACIONES", "EJECUCION", "WALLET")
PASOS_POR_DEFECTO = ("NINGUNO", "OPERACIONES", "EJECUCION", "WALLET")

REFERENCIA_PAGO = "saga:{saga_id}:autorizacion"
REFERENCIA_ACREDITACION = "saga:{saga_id}:acreditacion"


@dataclass
class Auditoria:
    saga_id: str
    fallo_pedido: str = ""
    estado_global: str = ""
    trabajo_id: str = ""
    paso_detenido: str = ""
    monto_pago: Decimal = Decimal(0)
    estado_pago: str = "SIN_PAGO"
    monto_acreditado: Decimal = Decimal(0)
    acreditaciones: int = 0
    problemas: list[str] = field(default_factory=list)

    @property
    def en_custodia(self) -> Decimal:
        """Dinero cobrado que todavía no llegó al proveedor y tiene justificación."""

        if self.estado_global == "EN_DISPUTA" and self.estado_pago == "Confirmado":
            return self.monto_pago
        return Decimal(0)

    @property
    def cobrado(self) -> Decimal:
        return self.monto_pago if self.estado_pago == "Confirmado" else Decimal(0)

    @property
    def desviacion(self) -> Decimal:
        """Cuánto se aparta esta saga de `cobrado = acreditado + custodia`.

        Positiva es dinero perdido (se cobró y no llegó a ninguna parte) y
        negativa es dinero fantasma (llegó al proveedor sin cobro que lo
        respalde). Se mide por saga y no solo en el agregado porque en el
        agregado una pérdida y un fantasma del mismo tamaño se cancelan entre sí
        y el total daría cero con dos errores adentro.
        """

        return self.cobrado - self.monto_acreditado - self.en_custodia


# --- Lanzamiento -----------------------------------------------------------------


def _lanzar(
    endpoints: Endpoints, num: int, monto_base: float, pasos: list[str], hilos: int, semilla: int
) -> list[tuple[str, str]]:
    """Lanza `num` sagas concurrentes con un fallo elegido al azar en cada una."""

    azar = random.Random(semilla)
    plan = [(indice, azar.choice(pasos)) for indice in range(num)]

    def una(entrada: tuple[int, str]):
        indice, paso = entrada
        respuesta = iniciar_saga(
            endpoints,
            # Un monto distinto por saga: si una acreditación se cruzara con otra,
            # el cotejo por monto lo delata además del cotejo por referencia.
            monto=monto_base + indice,
            cliente_id=f"cli-consistencia-{indice}",
            referencia_externa=f"CONS-{indice}-{uuid.uuid4().hex[:8]}",
            descripcion="Servicio sintético del experimento de consistencia",
            simular_fallo_en_paso=None if paso == "NINGUNO" else paso,
        )
        if respuesta.codigo == 202 and isinstance(respuesta.cuerpo, dict):
            return respuesta.cuerpo["saga_id"], paso
        print(f"     [aviso] saga {indice} rechazada (HTTP {respuesta.codigo})")
        return None

    with ThreadPoolExecutor(max_workers=min(hilos, num)) as pool:
        resultados = list(pool.map(una, plan))
    return [r for r in resultados if r]


def _esperar_cierre(endpoints: Endpoints, saga_ids: list[str], segundos: float) -> set[str]:
    limite_consulta = len(saga_ids) + 60
    pendientes = set(saga_ids)
    limite = time.perf_counter() + segundos
    while pendientes and time.perf_counter() < limite:
        time.sleep(2)
        respuesta = pedir(f"{endpoints.sagas}?limite={limite_consulta}")
        if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
            continue
        estados = {i["saga_id"]: i.get("estado_global", "") for i in respuesta.cuerpo}
        antes = len(pendientes)
        pendientes = {s for s in pendientes if not es_final(estados.get(s))}
        if len(pendientes) != antes:
            print(f"     cerradas {len(saga_ids) - len(pendientes)}/{len(saga_ids)}")
    return pendientes


# --- Lectura de las tres fuentes --------------------------------------------------


def _billetera_del_proveedor(endpoints: Endpoints) -> dict:
    respuesta = pedir(f"{endpoints.wallet}/billeteras?proveedor_id={PROVEEDOR_DE_LA_SAGA}")
    if not respuesta.ok or not isinstance(respuesta.cuerpo, dict):
        return {}
    items = respuesta.cuerpo.get("items") or []
    return items[0] if items else {}


def _movimientos_por_referencia(endpoints: Endpoints, billetera_id: str) -> dict[str, list[dict]]:
    respuesta = pedir(f"{endpoints.wallet}/billeteras/{billetera_id}/movimientos")
    indice: dict[str, list[dict]] = {}
    if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
        return indice
    for movimiento in respuesta.cuerpo:
        referencia = movimiento.get("referencia_externa")
        if referencia:
            indice.setdefault(referencia, []).append(movimiento)
    return indice


def _pago_de_la_saga(endpoints: Endpoints, trabajo_id: str, saga_id: str) -> dict:
    respuesta = pedir(f"{endpoints.pagos}/pagos?trabajo_id={trabajo_id}")
    if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
        return {}
    referencia = REFERENCIA_PAGO.format(saga_id=saga_id)
    for pago in respuesta.cuerpo:
        if pago.get("referencia_externa") == referencia:
            return pago
    return {}


# --- Reglas de consistencia -------------------------------------------------------


def _auditar_una(
    endpoints: Endpoints,
    saga_id: str,
    fallo_pedido: str,
    movimientos: dict[str, list[dict]],
) -> Auditoria:
    auditoria = Auditoria(saga_id=saga_id, fallo_pedido=fallo_pedido)

    saga = consultar_saga(endpoints, saga_id)
    if not saga:
        auditoria.problemas.append("la saga no existe en el Saga Log")
        return auditoria

    auditoria.estado_global = saga.get("estado_global", "?")
    auditoria.trabajo_id = saga.get("trabajo_id", "")
    if not es_final(auditoria.estado_global):
        auditoria.paso_detenido = paso_donde_quedo(saga)
        auditoria.problemas.append(f"no alcanzó un estado final ({auditoria.estado_global})")

    pago = _pago_de_la_saga(endpoints, auditoria.trabajo_id, saga_id)
    if pago:
        auditoria.estado_pago = pago.get("estado", "?")
        auditoria.monto_pago = Decimal(str(pago.get("monto", "0")))

    creditos = movimientos.get(REFERENCIA_ACREDITACION.format(saga_id=saga_id), [])
    auditoria.acreditaciones = len(creditos)
    auditoria.monto_acreditado = sum(
        (Decimal(str(m.get("monto", "0"))) for m in creditos), Decimal(0)
    )

    estado = auditoria.estado_global
    acreditada = auditoria.acreditaciones > 0

    if auditoria.acreditaciones > 1:
        auditoria.problemas.append(
            f"DINERO FANTASMA: {auditoria.acreditaciones} acreditaciones con la misma "
            "referencia (idempotencia rota)"
        )

    if estado == "COMPLETADA_EXITOSA":
        if auditoria.estado_pago != "Confirmado":
            auditoria.problemas.append(
                f"DINERO FANTASMA: saga exitosa con el pago en {auditoria.estado_pago}"
            )
        if not acreditada:
            auditoria.problemas.append(
                "DINERO PERDIDO: saga exitosa sin acreditación al proveedor"
            )
        elif auditoria.monto_acreditado != auditoria.monto_pago:
            auditoria.problemas.append(
                f"DESCUADRE DE MONTO: cobrado {auditoria.monto_pago} vs "
                f"acreditado {auditoria.monto_acreditado}"
            )

    elif estado == "COMPENSADA":
        if acreditada:
            auditoria.problemas.append(
                "DINERO FANTASMA: saga compensada pero el proveedor quedó acreditado"
            )
        if auditoria.estado_pago == "Confirmado":
            auditoria.problemas.append(
                "DINERO PERDIDO: saga compensada con el cobro todavía confirmado "
                "(la reversión no llegó)"
            )
        if auditoria.estado_pago not in {"Reversado", "Rechazado", "SIN_PAGO"}:
            auditoria.problemas.append(
                f"pago en un estado inesperado tras compensar: {auditoria.estado_pago}"
            )

    elif estado == "EN_DISPUTA":
        if acreditada:
            auditoria.problemas.append(
                "INCONSISTENTE: la saga se declaró en disputa pero la acreditación sí ocurrió"
            )
        if auditoria.estado_pago != "Confirmado":
            auditoria.problemas.append(
                f"INCONSISTENTE: disputa sin cobro que custodiar (pago {auditoria.estado_pago})"
            )

    elif estado == "FALLIDA":
        auditoria.problemas.append(
            "COMPENSACIÓN INCOMPLETA: la saga terminó FALLIDA; requiere revisión manual"
        )

    return auditoria


def _auditar(
    endpoints: Endpoints, sagas: list[tuple[str, str]], billetera_id: str, hilos: int
) -> list[Auditoria]:
    movimientos = _movimientos_por_referencia(endpoints, billetera_id) if billetera_id else {}
    with ThreadPoolExecutor(max_workers=min(hilos, 12)) as pool:
        return list(
            pool.map(
                lambda entrada: _auditar_una(endpoints, entrada[0], entrada[1], movimientos),
                sagas,
            )
        )


def _sagas_existentes(endpoints: Endpoints, limite: int) -> list[tuple[str, str]]:
    respuesta = pedir(f"{endpoints.sagas}?limite={limite}")
    if not respuesta.ok or not isinstance(respuesta.cuerpo, list):
        return []
    return [(i["saga_id"], "—") for i in respuesta.cuerpo]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--num", type=int, default=20, help="Sagas concurrentes a lanzar")
    parser.add_argument(
        "--pasos",
        default=",".join(PASOS_POR_DEFECTO),
        help=f"Pasos a hacer fallar al azar. Disponibles: {', '.join(PASOS_DISPONIBLES)}",
    )
    parser.add_argument("--monto-base", type=float, default=310000.0)
    parser.add_argument("--espera", type=float, default=120.0, help="Segundos para que cierren")
    parser.add_argument("--hilos", type=int, default=12)
    parser.add_argument("--semilla", type=int, default=7, help="Semilla del sorteo de fallos")
    parser.add_argument(
        "--solo-auditar", action="store_true", help="No lanza sagas: audita las que ya existen"
    )
    parser.add_argument("--limite", type=int, default=50, help="Sagas a auditar con --solo-auditar")
    parser.add_argument("--via", choices=["auto", "gateway", "directo"], default="auto")
    parser.add_argument("--csv", action="store_true")
    args = parser.parse_args()

    pasos = [p.strip().upper() for p in args.pasos.split(",") if p.strip()]
    desconocidos = [p for p in pasos if p not in PASOS_DISPONIBLES]
    if desconocidos:
        parser.error(f"pasos desconocidos: {', '.join(desconocidos)}")

    endpoints = resolver_endpoints_o_salir(args.via)

    titulo("Escenario de calidad — Consistencia transaccional bajo fallo concurrente")
    fila_metrica("Entrada usada", f"{endpoints.trabajos} ({endpoints.via})")

    billetera = _billetera_del_proveedor(endpoints)
    if not billetera:
        print()
        print(
            f"  [aviso] el proveedor {PROVEEDOR_DE_LA_SAGA} no tiene billetera en WalletBC.\n"
            "  Sin ella toda acreditación falla y las sagas terminan EN_DISPUTA. Verifique\n"
            "  que wallet arrancó con SEMBRAR_BILLETERAS activo."
        )
    saldo_inicial = Decimal(str(billetera.get("saldo", "0")))
    fila_metrica("Billetera del proveedor", billetera.get("id", "—"))
    fila_metrica("Saldo inicial", f"{saldo_inicial:,.2f} {billetera.get('moneda', '')}")

    if args.solo_auditar:
        sagas = _sagas_existentes(endpoints, args.limite)
        fila_metrica("Sagas a auditar (ya existentes)", len(sagas))
    else:
        fila_metrica("Sagas concurrentes", args.num)
        fila_metrica("Fallos sorteados entre", ", ".join(pasos))
        print()
        print(f"  1. Lanzando {args.num} sagas en paralelo…")
        sagas = _lanzar(endpoints, args.num, args.monto_base, pasos, args.hilos, args.semilla)
        print(f"     aceptadas {len(sagas)}/{args.num}")
        if not sagas:
            print("\n  Ninguna saga arrancó; no hay nada que auditar.")
            raise SystemExit(1)
        print(f"  2. Esperando el cierre de las sagas (hasta {args.espera:.0f}s)…")
        abiertas = _esperar_cierre(endpoints, [s for s, _ in sagas], args.espera)
        if abiertas:
            print(f"     [aviso] {len(abiertas)} sagas siguen abiertas; se auditan igual")

    if not sagas:
        print("\n  No hay sagas para auditar.")
        raise SystemExit(1)

    print()
    print("  3. Auditando Saga Log × PagosBC × WalletBC…")
    auditorias = _auditar(endpoints, sagas, billetera.get("id", ""), args.hilos)

    billetera_final = _billetera_del_proveedor(endpoints)
    saldo_final = Decimal(str(billetera_final.get("saldo", "0")))

    # --- Cuadre contable ---------------------------------------------------------
    cobrado = sum((a.cobrado for a in auditorias), Decimal(0))
    acreditado = sum((a.monto_acreditado for a in auditorias), Decimal(0))
    custodia = sum((a.en_custodia for a in auditorias), Decimal(0))
    descuadre = cobrado - acreditado - custodia
    descuadre_bruto = sum((abs(a.desviacion) for a in auditorias), Decimal(0))
    sagas_descuadradas = [a for a in auditorias if a.desviacion != 0]
    movimiento_de_saldo = saldo_final - saldo_inicial

    por_estado: dict[str, int] = {}
    for auditoria in auditorias:
        por_estado[auditoria.estado_global] = por_estado.get(auditoria.estado_global, 0) + 1

    con_problemas = [a for a in auditorias if a.problemas]

    titulo("Desenlaces de las sagas auditadas")
    for estado, cuantas in sorted(por_estado.items()):
        fila_metrica(estado, cuantas)

    titulo("Cuadre contable")
    fila_metrica("Cobrado al cliente (pagos Confirmados)", f"{cobrado:,.2f}")
    fila_metrica("Acreditado al proveedor", f"{acreditado:,.2f}")
    fila_metrica("En custodia (sagas EN_DISPUTA)", f"{custodia:,.2f}")
    print("  " + "-" * 60)
    fila_metrica("Discrepancia neta", f"{descuadre:,.2f}", "= 0")
    fila_metrica(
        "Discrepancia bruta (suma de |desvío| por saga)",
        f"{descuadre_bruto:,.2f} en {len(sagas_descuadradas)} saga(s)",
        "= 0",
    )
    if descuadre_bruto != 0 and descuadre != descuadre_bruto:
        print(
            "      └─ la neta es menor que la bruta: hay pérdidas y fantasmas que se\n"
            "         cancelan entre sí. La cifra que vale es la bruta."
        )
    print()
    fila_metrica("Saldo de la billetera: inicio → fin", f"{saldo_inicial:,.2f} → {saldo_final:,.2f}")
    fila_metrica(
        "Movimiento del saldo vs. acreditado",
        f"{movimiento_de_saldo:,.2f} vs {acreditado:,.2f}",
        "iguales",
    )

    if con_problemas:
        titulo(f"Discrepancias encontradas ({len(con_problemas)} sagas)")
        for auditoria in con_problemas:
            print(
                f"  [X] {auditoria.saga_id[:8]}… fallo_pedido={auditoria.fallo_pedido:<11} "
                f"estado={auditoria.estado_global:<19} pago={auditoria.estado_pago:<11} "
                f"acreditaciones={auditoria.acreditaciones} desvío={auditoria.desviacion:,.2f}"
            )
            for problema in auditoria.problemas:
                print(f"       └─ {problema}")
    else:
        titulo("Sin discrepancias")
        print("  Cada saga auditada cuadra con su pago y con su acreditación.")

    titulo("Veredicto del escenario")
    veredicto("Discrepancia bruta estrictamente 0", descuadre_bruto == 0)
    veredicto("Sin dinero fantasma ni perdido en ninguna saga", not con_problemas)
    veredicto(
        "El saldo de la billetera se movió solo por estas acreditaciones",
        movimiento_de_saldo == acreditado,
    )
    veredicto(
        "Ninguna saga terminó FALLIDA (compensación incompleta)",
        por_estado.get("FALLIDA", 0) == 0,
    )
    veredicto(
        "Toda acreditación ocurrió exactamente una vez",
        all(a.acreditaciones <= 1 for a in auditorias),
    )

    if args.csv:
        ruta = Path.cwd() / f"consistencia-{marca_de_tiempo()}.csv"
        escribir_csv(
            ruta,
            [
                "saga_id",
                "fallo_pedido",
                "estado_global",
                "estado_pago",
                "monto_pago",
                "acreditaciones",
                "monto_acreditado",
                "en_custodia",
                "desviacion",
                "problemas",
            ],
            [
                [
                    a.saga_id,
                    a.fallo_pedido,
                    a.estado_global,
                    a.estado_pago,
                    f"{a.monto_pago}",
                    a.acreditaciones,
                    f"{a.monto_acreditado}",
                    f"{a.en_custodia}",
                    f"{a.desviacion}",
                    " | ".join(a.problemas),
                ]
                for a in auditorias
            ],
        )
        print()
        fila_metrica("Detalle por saga", ruta)

    if con_problemas or descuadre_bruto != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
