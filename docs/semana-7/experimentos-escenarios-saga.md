# Experimentos de los escenarios de calidad de la Saga

## Proyecto: Hogar de los Alpes

Protocolo de ejecución de los tres escenarios de calidad que se evalúan sobre la
**Saga de Activación de Servicio**: elasticidad ante picos, disponibilidad ante la
caída del broker y consistencia transaccional bajo fallo concurrente.

Los tres experimentos están automatizados en `gestion-trabajos-service/scripts/` y
miden el sistema **desde afuera, por HTTP**, que es la vista que tiene un cliente
real. Cada uno imprime sus métricas y un veredicto explícito por hipótesis, y
puede volcar el detalle por saga a CSV con `--csv` para pegarlo en el informe.

| Escenario | Script | Qué derriba o fuerza |
|---|---|---|
| 1 — Elasticidad | `scripts/carga_elasticidad_sagas.py` | Rampa de carga hasta 4x la línea base |
| 2 — Disponibilidad | `scripts/prueba_disponibilidad_pulsar.py` | Congela o mata el contenedor de Pulsar |
| 3 — Consistencia | `scripts/auditoria_consistencia_sagas.py` | Fallos aleatorios en pasos posteriores al pago |

---

## 0. Preparación del ambiente

Los tres scripts solo usan la biblioteca estándar de Python (3.10+), así que en la
VM no hay que instalar nada más allá de Docker.

```bash
# En la raíz del repositorio
docker compose up -d --build --wait
curl http://localhost/salud                       # {"estado":"ok"}
```

Para una corrida limpia y comparable, arranque de cero: así las bases quedan
vacías, WalletBC vuelve a sembrar la billetera de `prov-hda-expert-01` y el Saga
Log no arrastra sagas de ejecuciones anteriores.

```bash
docker compose down -v && docker compose up -d --build --wait
```

Los scripts se corren **desde la propia máquina** (por SSH si es la EC2), porque
las APIs directas y Pulsar están ligadas a `127.0.0.1` y solo el gateway escucha
en el puerto 80. Se ejecutan desde `gestion-trabajos-service/`:

```bash
cd gestion-trabajos-service
python3 -m scripts.carga_elasticidad_sagas --help
```

Detectan solos por dónde hablar (gateway y, si no responde, puertos directos).
Si el gateway está en otro puerto, exporte `PUERTO_GATEWAY=8088` o fuerce la vía
con `--via directo`.

**Dimensionamiento de la instancia.** El stack en reposo consume unos 2,9 GiB
(Pulsar se lleva 2,4). Para los escenarios 2 y 3 basta `t3.large` (2 vCPU / 8 GiB);
para el escenario 1 con `--base 5` o más, use `t3.xlarge` (4 vCPU / 16 GiB): si la
VM se queda sin CPU, lo que se mide es el límite de la VM y no el de la
arquitectura, y el informe queda sin valor.

### Orden recomendado

1. **Elasticidad** sobre el stack recién levantado.
2. **Consistencia**, que necesita un cuadre contable limpio.
3. **Disponibilidad** de último, porque deja sagas detenidas a propósito.
4. `auditoria_consistencia_sagas --solo-auditar` después del 2, para cuantificar
   en pesos lo que dejó la caída del broker.

---

## 1. Escenario de Elasticidad — picos de demanda

**Hipótesis.** Ante un evento climático que multiplica por cuatro la llegada de
solicitudes, el sistema sigue aceptándolas en tiempo interactivo y termina las
sagas sin acumular trabajo pendiente.

**Por qué se miden dos latencias.** `POST /sagas/activar-servicio` responde `202`
apenas crea el trabajo preliminar y publica el comando de pago; el resto de la
saga ocurre después, por Pulsar. Confundir ambas latencias sería el error clásico
al medir una arquitectura asíncrona:

- **Aceptación (HTTP):** lo que espera el partner. Medida en el cliente.
- **Extremo a extremo (saga):** la transacción distribuida completa, calculada con
  las marcas de tiempo del propio Saga Log (`fecha_actualizacion − fecha_creacion`),
  de modo que el intervalo de sondeo del script no la contamina.

**Saturación** es la fracción de sagas que, agotado el drenaje, siguen en un estado
no final: el sistema aceptó el trabajo pero no lo terminó. Es la métrica que
delata el punto de quiebre, y la que hay que vigilar al subir `--base`.

```bash
cd gestion-trabajos-service

# Rampa por defecto: 2 → 4 → 6 → 8 sagas/s, 20 s por etapa (400 sagas)
python3 -m scripts.carga_elasticidad_sagas --csv

# Línea base más alta y etapas más largas
python3 -m scripts.carga_elasticidad_sagas --base 5 --duracion 30 --drenaje 150 --csv

# Solo línea base contra pico, para una gráfica de dos barras
python3 -m scripts.carga_elasticidad_sagas --multiplicadores 1,4 --csv
```

El script calienta con una saga completa antes de empezar: la primera saga de un
Pulsar recién arrancado paga la creación de los seis tópicos y sus suscripciones,
y cobrárselo a la etapa 1 falsearía la línea base. Se desactiva con
`--sin-calentamiento`.

**Umbrales evaluados:** aceptación p95 < 500 ms, p99 < 1000 ms, saturación < 1 %, y
ritmo logrado ≥ 90 % del objetivo en el pico.

**Comparación con dos réplicas del orquestador** (el mismo experimento que
sustenta el escenario de escalabilidad, ahora sobre la saga completa):

```bash
docker compose --profile escalabilidad up -d --build gestion-trabajos-2
cd gestion-trabajos-service && python3 -m scripts.carga_elasticidad_sagas --base 5 --csv
```

Ambas réplicas comparten la suscripción `Shared` sobre `comandos-trabajo` y la
misma base, así que Pulsar reparte la carga sin ningún cambio de código.

### Tabla para el informe

| Etapa | Objetivo (sagas/s) | Logrado | req/s | Aceptación p50/p95/p99 (ms) | Saga p50/p95 (s) | Saturación |
|---|---|---|---|---|---|---|
| 1x | | | | | | |
| 2x | | | | | | |
| 3x | | | | | | |
| 4x | | | | | | |

---

## 2. Escenario de Disponibilidad — caída de Apache Pulsar

**Hipótesis.** Si el broker se cae con sagas en tránsito, ninguna se pierde: al
restablecerlo avanzan solas hasta un estado final, y mientras tanto el Saga Log
sigue consultable.

El experimento derribará el broker de dos formas que dan resultados
deliberadamente distintos, y esa diferencia es el resultado interesante:

| Modo | Qué hace | Ledgers | Lo que se espera |
|---|---|---|---|
| `pausa` (por defecto) | `docker pause` | se conservan | Partición de red o pausa de GC: los mensajes publicados siguen ahí y deberían entregarse al reanudar |
| `caida` | `docker compose kill` + `up -d` | se borran | Pérdida total de lo que estaba en vuelo |

El modo `caida` no es un defecto del experimento sino del despliegue, y conviene
decirlo así en el informe: Pulsar arranca en standalone con `rm -rf /pulsar/data/*`
(ver `docker-compose.yml`) porque un bookie que cambia de dirección no puede
recuperar sus ledgers anteriores. Es una decisión consciente de la POC con una
consecuencia medible.

```bash
cd gestion-trabajos-service

# Partición temporal de 25 s con 12 sagas en vuelo
python3 -m scripts.prueba_disponibilidad_pulsar --modo pausa --csv

# Caída dura con pérdida de ledgers
python3 -m scripts.prueba_disponibilidad_pulsar --modo caida --num 20 --espera-caido 40 --csv
```

Requiere permisos de Docker (en EC2, el usuario en el grupo `docker`).

**Métricas que reporta:** sagas retenidas por la caída, recuperadas
automáticamente vs. no recuperadas, tiempo hasta que el broker vuelve a estar
`healthy`, percentiles del tiempo de recuperación de cada saga medido desde ese
instante, y el paso exacto donde quedaron detenidas las que no volvieron.

Además sondea la API con el broker caído y reporta dos códigos HTTP por separado,
porque son dos preguntas distintas: **leer** el Saga Log solo toca Postgres, mientras
que **iniciar** una saga necesita publicar en Pulsar. La diferencia entre ambas
respuestas es el radio de impacto real de la caída.

### Dos límites conocidos que este experimento deja a la vista

1. **No hay Outbox.** Los eventos de dominio se publican después de confirmar la
   transacción; si el broker cae en esa ventana, el evento se pierde sin que nadie
   lo reintente. Es la causa de que el modo `caida` recupere tan poco.
2. **El consumidor de eventos de saga confirma el mensaje aunque el manejo falle**
   (`consumidor_eventos_saga_pulsar.py:82-87`): un evento cuyo comando siguiente no
   se pueda publicar queda *ack*-eado y la saga se detiene en ese paso. En la
   corrida del 2026-09-21 este riesgo **no** se materializó —el modo `pausa`
   recuperó el 100 %—, porque con el broker congelado el consumidor no recibe nada
   y ningún manejador llega a correr. La ventana exige un broker *parcialmente*
   disponible, lo que la vuelve difícil de reproducir y fácil de subestimar.

### Resultados de referencia (portátil, 2026-09-21)

Para saber si una corrida nueva se sale de lo esperado:

| Modo | Retenidas | Recuperadas | Broker sano en | Recuperación de sagas |
|---|---|---|---|---|
| `pausa` | 9 de 12 | 9 (100 %) | 14,4 s | 2,0 s p50/máx |
| `caida` | 17 de 20 | 2 (12 %) | 10,4 s | 12,2 s p50/máx |

En ambos modos el Saga Log respondió `HTTP 200` durante toda la caída, mientras que
iniciar una saga nueva dio timeout. Las 15 sagas no recuperadas del modo `caida`
quedaron detenidas en `5:ACREDITAR_PROVEEDOR`.

### Tabla para el informe

| Modo | Sagas en vuelo | Retenidas | Recuperadas | No recuperadas | Broker sano en (s) | Recuperación p50/máx (s) | Leer / Iniciar durante la caída |
|---|---|---|---|---|---|---|---|
| `pausa` | | | | | | | |
| `caida` | | | | | | | |

---

## 3. Escenario de Consistencia transaccional bajo fallo concurrente

**Hipótesis.** Con sagas concurrentes fallando en puntos distintos después de la
retención del pago, la discrepancia entre el dinero y el Saga Log es exactamente
`0`: ningún peso queda fantasma ni perdido.

El script cruza tres fuentes que viven en **tres bases de datos distintas**, que es
justamente lo que hace no trivial la pregunta:

| Fuente | Consulta | Clave de cotejo |
|---|---|---|
| Saga Log (GestionDeTrabajosBC) | `GET /sagas/{id}` | `saga_id` |
| Pago (PagosBC) | `GET /pagos?trabajo_id=…` | `saga:{saga_id}:autorizacion` |
| Movimiento (WalletBC) | `GET /billeteras/{id}/movimientos` | `saga:{saga_id}:acreditacion` |

Cada saga lleva un monto distinto, de modo que un cruce entre acreditaciones se
delataría por monto además de por referencia.

**La identidad contable que se verifica:**

```
cobrado = acreditado + en custodia (sagas EN_DISPUTA)
```

`EN_DISPUTA` **no** es un descuadre: es custodia declarada. El servicio ya se
prestó, el cobro se sostiene y el Saga Log deja constancia de que Operaciones debe
resolverlo a mano. El descuadre sería custodia sin saga que la respalde.

**Reporte la discrepancia bruta, no la neta.** La identidad se evalúa saga por
saga y el script reporta las dos cifras, porque en el agregado un peso perdido y
un peso fantasma del mismo tamaño se cancelan: es perfectamente posible tener una
discrepancia neta de `0.00` con varias sagas rotas adentro. La cifra que sostiene
la hipótesis es la **bruta** (suma de los desvíos en valor absoluto), y es la que
usa el veredicto y el código de salida.

**Invariantes verificadas saga por saga:**

| Estado final | Pago esperado | Acreditación | Dinero |
|---|---|---|---|
| `COMPLETADA_EXITOSA` | `Confirmado` | sí, por el monto exacto | liquidado al proveedor |
| `COMPENSADA` | `Reversado` o `Rechazado` | ninguna | cero |
| `EN_DISPUTA` | `Confirmado` | ninguna | en custodia, declarada |
| `FALLIDA` | — | — | compensación incompleta: se reporta |

Lo que el script marca como discrepancia:

- **Dinero fantasma:** acreditación sin cobro confirmado, saga compensada con el
  proveedor acreditado, o más de una acreditación con la misma referencia
  (idempotencia rota).
- **Dinero perdido:** saga exitosa sin acreditación, o saga compensada con el cobro
  todavía confirmado porque la reversión nunca llegó.
- **Descuadre de monto** entre lo cobrado y lo acreditado.

```bash
cd gestion-trabajos-service

# 20 sagas concurrentes, fallo sorteado entre NINGUNO/OPERACIONES/EJECUCION/WALLET
python3 -m scripts.auditoria_consistencia_sagas --num 20 --csv

# Solo pasos posteriores a la retención del pago, más volumen
python3 -m scripts.auditoria_consistencia_sagas --num 40 --pasos OPERACIONES,EJECUCION,WALLET --csv

# Auditar lo que ya existe (por ejemplo, después del escenario 2)
python3 -m scripts.auditoria_consistencia_sagas --solo-auditar --limite 100 --csv
```

El sorteo de fallos es reproducible: `--semilla` fija el reparto, así que dos
corridas con la misma semilla comparan manzanas con manzanas.

Como control adicional, el script contrasta el saldo de la billetera antes y
después: el movimiento del saldo debe ser exactamente la suma de las
acreditaciones de estas sagas, ni un peso más.

**Código de salida 1** si encuentra cualquier discrepancia, de modo que sirve tal
cual como puerta de calidad en CI.

### Tabla para el informe

| Corrida | Sagas | Exitosas | Compensadas | En disputa | Fallidas | Cobrado | Acreditado | Custodia | Discrep. neta | **Discrep. bruta** |
|---|---|---|---|---|---|---|---|---|---|---|
| Fallos posteriores al pago | | | | | | | | | | |
| Incluyendo fallo en pago | | | | | | | | | | |
| Tras la caída del broker | | | | | | | | | | |

---

## Interpretación y amenazas a la validez

- **Mida en la VM, no desde su equipo.** Los scripts asumen `127.0.0.1` a
  propósito. Correrlos por internet mezclaría la latencia de red con la del
  sistema, y además los puertos internos no están publicados.
- **`localhost` cuesta dos segundos por petición** en los puertos directos: al no
  haber listener IPv6, el cliente intenta `::1` primero. Por eso los scripts usan
  `127.0.0.1` explícitamente.
- **Una sola corrida no es un resultado.** Repita tres veces cada escenario y
  reporte la mediana; la primera corrida tras `docker compose up` siempre es la
  más lenta.
- **Pulsar en standalone no es Pulsar en producción.** Un clúster real con tres
  bookies sobrevive a la caída de un broker sin perder ledgers. El escenario 2 mide
  este despliegue, y las conclusiones deben decirlo.
- **El fallo se simula en el participante, no en el orquestador.**
  `simular_fallo_en_paso` hace que PagosBC, OperacionesBC o WalletBC respondan con
  el evento de rechazo. Es fiel para probar las compensaciones, pero no cubre la
  caída del orquestador a mitad de saga, que hoy no tiene recuperación al arrancar.

## Dónde queda cada evidencia

- Salida en consola con el veredicto por hipótesis: pegar en
  `informe-experimentacion.md`, secciones 4 y 6.
- CSV por saga (`--csv`, en el directorio desde el que corra el script): insumo de
  las gráficas de latencia y de la tabla de cuadre contable.
- Saga Log completo de cualquier saga citada: `GET /trabajos/sagas/{saga_id}`.
