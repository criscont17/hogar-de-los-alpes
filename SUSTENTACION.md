# Sustentación — Escenarios de Calidad sobre la Saga

## Proyecto: Hogar de los Alpes

Documento de sustentación de los tres escenarios de calidad evaluados sobre la
**Saga de Activación de Servicio**: elasticidad ante picos, disponibilidad ante la
caída del broker y consistencia transaccional bajo fallo concurrente.

> **Estado de este documento.** El análisis cualitativo, las hipótesis, los
> criterios de aceptación y el guion del video están completos. Las celdas
> marcadas `⟨…⟩` esperan los números de la corrida real: se llenan copiando la
> salida de los tres scripts (§1.2). Ningún número de este documento debe
> inventarse — un dato sin corrida que lo respalde invalida la sustentación
> entera. El único veredicto anticipado es el de la Hipótesis 2, y está marcado
> como **predicción derivada del código**, no como resultado medido.

---

## 1. Metodología

### 1.1 Ambiente de ejecución

| Elemento | Valor |
|---|---|
| Infraestructura | ⟨EC2 `t3.large` / `t3.xlarge` / portátil⟩ |
| vCPU / RAM | ⟨2 vCPU / 8 GiB⟩ |
| Sistema operativo | ⟨Ubuntu 24.04 LTS x86_64⟩ |
| Versión de Docker | ⟨`docker --version`⟩ |
| Consumo del stack en reposo | ~2,9 GiB de RAM (Pulsar 2,4 GiB); imágenes ~2,6 GB |
| Servicios desplegados | 5 servicios + 4 PostgreSQL + Pulsar standalone + gateway Nginx |
| Fecha de la corrida | ⟨AAAA-MM-DD⟩ |

Los experimentos se ejecutan **desde la propia máquina** que hospeda el stack: las
APIs directas, las bases y Pulsar están ligadas a `127.0.0.1` y solo el gateway
escucha en el puerto 80. Se usa `127.0.0.1` y no `localhost` porque, al no haber
listener IPv6, un cliente que resuelva `localhost` intenta `::1` primero y pierde
unos dos segundos por petición — suficiente para arruinar cualquier medición.

### 1.2 Instrumentación

Los tres experimentos están automatizados y solo usan la biblioteca estándar de
Python, de modo que la VM no necesita dependencias adicionales. Miden el sistema
**desde afuera, por HTTP**, que es la vista de un cliente real.

```bash
# Punto de partida limpio: bases vacías, billetera del proveedor resembrada,
# Saga Log sin arrastres de corridas anteriores.
docker compose down -v && docker compose up -d --build --wait

cd gestion-trabajos-service
python3 -m scripts.carga_elasticidad_sagas --csv                       # Escenario 1
python3 -m scripts.auditoria_consistencia_sagas --num 20 --csv         # Escenario 3
python3 -m scripts.prueba_disponibilidad_pulsar --modo pausa --csv     # Escenario 2a
python3 -m scripts.prueba_disponibilidad_pulsar --modo caida --num 20 --csv  # Escenario 2b
python3 -m scripts.auditoria_consistencia_sagas --solo-auditar --limite 100  # secuela del 2
```

El protocolo completo, los umbrales y las amenazas a la validez están en
[`docs/semana-7/experimentos-escenarios-saga.md`](docs/semana-7/experimentos-escenarios-saga.md).

**Tres decisiones de medición que condicionan la lectura de los resultados:**

1. **Se separan dos latencias.** `POST /sagas/activar-servicio` responde `202`
   apenas crea el trabajo preliminar y publica el comando de pago; el resto de la
   saga ocurre después, por Pulsar. La *latencia de aceptación* es lo que percibe
   el partner; la *latencia extremo a extremo* es la transacción distribuida
   completa, calculada con las marcas de tiempo del propio Saga Log
   (`fecha_actualizacion − fecha_creacion`) para que el intervalo de sondeo del
   script no la contamine. Confundirlas sería el error clásico al medir una
   arquitectura asíncrona.
2. **Se reporta la discrepancia bruta, no la neta.** En el agregado, un peso
   perdido y un peso fantasma del mismo tamaño se cancelan: es posible obtener una
   discrepancia neta de `0.00` con varias sagas rotas adentro. La cifra que
   sostiene la hipótesis es la suma de los desvíos **en valor absoluto**.
3. **Cada saga lleva un monto distinto**, de modo que un cruce entre acreditaciones
   se delataría por monto además de por referencia.

### 1.3 Repetición

Cada escenario se corre **tres veces** y se reporta la mediana. La primera corrida
tras `docker compose up` siempre es la más lenta: la primera saga de un Pulsar
recién arrancado paga la creación de los seis tópicos y sus suscripciones. Por eso
el script de elasticidad calienta con una saga completa antes de medir.

---

## 2. Resultados cuantitativos

### 2.1 Escenario 1 — Elasticidad ante picos de demanda

Rampa de ⟨2⟩ sagas/s de línea base hasta 4x, ⟨20⟩ s por etapa, sin pausa entre
etapas (un pico real no hace pausas).

| Etapa | Objetivo (sagas/s) | Logrado (sagas/s) | Throughput (req/s) | Aceptación p50 (ms) | p95 (ms) | p99 (ms) | Saga p50 (s) | Saga p95 (s) | Saturación |
|---|---|---|---|---|---|---|---|---|---|
| 1x (línea base) | ⟨2,00⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 2x | ⟨4,00⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 3x | ⟨6,00⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| **4x (pico)** | ⟨8,00⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

**Degradación 1x → 4x:** aceptación p95 ⟨…⟩ ms → ⟨…⟩ ms (×⟨…⟩); saga completa p95
⟨…⟩ s → ⟨…⟩ s (×⟨…⟩). Sagas iniciadas en total: ⟨…⟩. Desenlaces en el pico:
⟨COMPLETADA_EXITOSA=…⟩.

**Comparación de escalado horizontal** (una réplica del orquestador contra dos,
con `--profile escalabilidad`; ambas comparten la suscripción `Shared` sobre
`comandos-trabajo`):

| Réplicas de GestionDeTrabajos | Ritmo logrado en el pico | Aceptación p95 | Saga p95 | Saturación |
|---|---|---|---|---|
| 1 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 2 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

### 2.2 Escenario 2 — Disponibilidad ante la caída de Apache Pulsar

Dos modos de derribo con resultados deliberadamente distintos:

| Modo | Qué hace | Ledgers | Qué representa |
|---|---|---|---|
| `pausa` | `docker pause` | se conservan | Partición de red o pausa de GC larga |
| `caida` | `docker compose kill` + `up -d` | se borran | Reinicio del standalone con datos limpios |

| Métrica | `pausa` | `caida` |
|---|---|---|
| Sagas puestas en tránsito | ⟨12⟩ | ⟨20⟩ |
| Cerradas antes de la caída | ⟨…⟩ | ⟨…⟩ |
| **Retenidas por la caída** | ⟨…⟩ | ⟨…⟩ |
| **Recuperadas automáticamente** | ⟨… (…%)⟩ | ⟨… (…%)⟩ |
| No recuperadas | ⟨…⟩ | ⟨…⟩ |
| Tiempo hasta broker `healthy` | ⟨…⟩ s | ⟨…⟩ s |
| Recuperación de sagas p50 / máx | ⟨…⟩ / ⟨…⟩ s | ⟨…⟩ / ⟨…⟩ s |
| **Recuperación total** (caída → última saga) | ⟨…⟩ s | ⟨…⟩ s |
| Leer el Saga Log durante la caída | HTTP ⟨200⟩ | HTTP ⟨200⟩ |
| Iniciar una saga durante la caída | HTTP ⟨…⟩ | HTTP ⟨…⟩ |

**Paso donde quedaron detenidas las no recuperadas:** ⟨p. ej. `2:AUTORIZAR_PAGO`⟩.

**Impacto en dinero de la caída** (corriendo la auditoría del escenario 3 sobre
las sagas afectadas, con `--solo-auditar`):

| Métrica | Valor |
|---|---|
| Sagas sin estado final tras el corte | ⟨…⟩ |
| Cobrado sin liquidar ni revertir | ⟨…⟩ COP |
| Discrepancia bruta atribuible al corte | ⟨…⟩ COP |

### 2.3 Escenario 3 — Consistencia transaccional bajo fallo concurrente

Sagas concurrentes con el paso que falla sorteado al azar (semilla fija para que
dos corridas sean comparables).

| Corrida | Sagas | Exitosas | Compensadas | En disputa | Fallidas | Cobrado | Acreditado | Custodia | Discrep. neta | **Discrep. bruta** |
|---|---|---|---|---|---|---|---|---|---|---|
| Fallos posteriores al pago (`OPERACIONES,EJECUCION,WALLET,NINGUNO`) | ⟨20⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨**0,00**⟩ |
| Incluyendo fallo en el pago (`PAGO`) | ⟨20⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨**0,00**⟩ |
| Tras la caída del broker | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

**Comprobaciones adicionales del auditor:**

| Comprobación | Resultado |
|---|---|
| Movimiento del saldo de la billetera = suma de acreditaciones | ⟨CUMPLE⟩ |
| Toda acreditación ocurrió exactamente una vez (idempotencia) | ⟨CUMPLE⟩ |
| Ninguna saga terminó `FALLIDA` (compensación incompleta) | ⟨CUMPLE⟩ |

**Invariantes verificadas saga por saga:**

| Estado final | Pago esperado | Acreditación | Interpretación del dinero |
|---|---|---|---|
| `COMPLETADA_EXITOSA` | `Confirmado` | sí, por el monto exacto | Liquidado al proveedor |
| `COMPENSADA` | `Reversado` o `Rechazado` | ninguna | Cero: nada quedó retenido |
| `EN_DISPUTA` | `Confirmado` | ninguna | En custodia, **declarada** en el Saga Log |
| `FALLIDA` | — | — | Compensación incompleta: se reporta como discrepancia |

---

## 3. Resultados cualitativos

### 3.1 Desacoplamiento

**Los bounded contexts nunca se llaman entre sí.** La única excepción es el BFF,
que consume contratos REST publicados. Todo lo demás viaja por Pulsar con
contratos versionados. La consecuencia observable durante los experimentos es que
el escenario 2 pudo derribar el broker sin tocar ningún servicio: no hubo que
reconfigurar clientes HTTP ni reiniciar contenedores, porque no existe una llamada
directa entre contextos que pudiera quedar colgada.

**El orquestador no conoce el dominio de los participantes.** Emite
`AutorizarPagoTrabajoV1`, `AsignarProveedorTrabajoV1` y `AcreditarProveedorV1`, y
reacciona a los eventos de respuesta. No sabe qué es un PSP, ni cómo se elige un
proveedor, ni qué reglas tiene una billetera. La prueba práctica: el paso 5 pasó de
"acreditar" a "acreditar solo si la billetera está activa, con reintentos y
backoff" sin una sola línea de cambio en el orquestador — la política vive entera
en WalletBC, que es quien sabe distinguir un fallo transitorio de uno permanente.

**El core no conoce partners.** A GestionDeTrabajos solo llega el comando canónico
con las condiciones ya resueltas; formatos y acuerdos viven en OperacionesBC. Por
eso el experimento de elasticidad puede generar carga sintética con un
`partner_id` que ni siquiera está registrado (`seguros-bolivar`) sin que el core se
inmute: no lo consulta.

**Dónde sí hay acoplamiento, y es deliberado:** los cinco pasos y sus
compensaciones están codificados en `OrquestadorSagaTrabajo`. Es el costo aceptado
de la orquestación frente a la coreografía, y se paga a cambio de que exista un
único lugar donde leer el flujo completo y un único lugar donde cambiarlo.

### 3.2 Tolerancia a fallos

**Compensación encadenada por confirmación, no por optimismo.** Cada compensación
se pide solo cuando llega el evento que confirma la anterior:
`LiberarAsignacionProveedorV1` → (se espera `AsignacionProveedorLiberadaV1`) →
`RevertirPagoTrabajoV1` → (se espera `PagoTrabajoRevertidoV1`) → cancelar el
trabajo. Si una confirmación no llega o llega negativa, la saga termina `FALLIDA`
en vez de dar por buena una reversión que nunca ocurrió. Por eso el escenario 3
trata cualquier `FALLIDA` como discrepancia: es la señal de que una compensación
quedó a medias.

**Lo ya ejecutado no se compensa.** El paso 5 es el único irreversible: cuando la
acreditación falla definitivamente, el trabajo pasa a `EN_DISPUTA` en lugar de
revertir el pago, porque el cliente ya recibió el servicio. Esta es la decisión de
diseño que más se nota en los resultados del escenario 3: `EN_DISPUTA` aparece en
la tabla como **custodia declarada** y no como descuadre. Un sistema que
"cuadrara" revirtiendo el cobro de un servicio prestado estaría perdiendo dinero
real a cambio de una métrica bonita.

**Aislamiento por participante.** Cada PSP vive detrás de un adaptador con su
propio circuit breaker, y un suscriptor que falla no arrastra a los demás: el
dispatcher aísla y registra. Los reintentos con backoff de la acreditación
(3 intentos, 0,5 s, factor 2) distinguen el fallo transitorio —una billetera
bloqueada que puede reactivarse— del permanente —el proveedor no tiene billetera,
la moneda no corresponde—, y este último no se reintenta: solo retrasaría la
disputa.

**Dos límites conocidos, que el escenario 2 vuelve medibles en lugar de dejarlos
en el papel:**

1. **No hay Outbox.** Los eventos de integración se publican después de confirmar
   la transacción. Si el broker cae en esa ventana, el evento se pierde y nadie lo
   reintenta.
2. **El consumidor de eventos de saga confirma el mensaje aunque el manejo falle**
   (`gestion-trabajos-service/app/infraestructura/adaptadores/entrada/mensajeria/consumidor_eventos_saga_pulsar.py:82-87`).
   Si el orquestador no logra publicar el comando siguiente porque el broker está
   caído, ese evento queda *ack*-eado y la saga se detiene en ese paso aunque el
   broker vuelva. Cambiar ese `acknowledge` por un `negative_acknowledge` ante
   fallas técnicas es la corrección mínima para que el modo `pausa` recupere el
   100 %.

Conviene también decir en la sustentación que **Pulsar en standalone no es Pulsar
en producción**: un clúster real con tres bookies sobrevive a la caída de un
broker sin perder ledgers. El escenario 2 mide este despliegue, y la conclusión
debe acotarse a él.

### 3.3 Observabilidad del Saga Log

El Saga Log (`saga_instancias`, `saga_pasos`) no es un log de depuración: es el
registro de negocio que hace auditable una transacción que no tiene una sola
base de datos donde mirar.

**Qué hizo posible en los experimentos —y que sin él no se habría podido medir:**

- **Latencia extremo a extremo exacta.** `fecha_actualizacion − fecha_creacion` son
  marcas del servidor: la latencia de la saga no depende de cada cuánto sondee el
  script. Sin el log habría que inferirla del intervalo de polling, con un error
  del orden del intervalo mismo.
- **Distinguir "lento" de "atascado".** La tasa de saturación del escenario 1 y las
  "sagas retenidas" del escenario 2 son la misma consulta: cuáles no llegaron a un
  estado final. El estado global es explícito, no se deduce.
- **Ubicar dónde se cortó la cadena.** Cuando una saga no se recupera, el log dice
  en qué paso quedó (`EN_PROCESO` sin cerrar) y con qué comando. Eso es lo que
  convirtió "algunas sagas no volvieron" en "quedaron detenidas en
  `AUTORIZAR_PAGO` porque el evento se perdió", que es un diagnóstico accionable.
- **Cotejar dinero contra intención.** El escenario 3 cruza tres bases distintas
  usando las referencias `saga:{id}:autorizacion` y `saga:{id}:acreditacion`. El
  Saga Log es la única fuente que dice cuál *debía* ser el desenlace; PagosBC y
  WalletBC solo dicen qué pasó con su parte.

**Superficie de consulta:** `GET /sagas` lista las transacciones recientes con su
estado global y `GET /sagas/{id}` devuelve el detalle paso a paso con comando
enviado, evento recibido, error y marcas de tiempo. Los cuatro estados finales
—`COMPLETADA_EXITOSA`, `COMPENSADA`, `EN_DISPUTA`, `FALLIDA`— son un vocabulario
cerrado, lo que permite automatizar el veredicto en vez de leerlo a ojo.

**Límite actual:** el log registra lo que el orquestador hizo, pero no lo
resucita. No hay un proceso que, al arrancar, retome las sagas que quedaron
abiertas. Es exactamente el hueco que el escenario 2 mide, y la corrección
natural es un *reaper* que relea las sagas no finales y reemita el comando
pendiente, apoyándose en la idempotencia que los participantes ya tienen.

---

## 4. Conclusiones sobre las hipótesis

Cada hipótesis se declara con su criterio de aceptación **numérico y fijado de
antemano**, de modo que el veredicto no dependa de la interpretación.

### Hipótesis 1 — Elasticidad

> **Enunciado.** Ante un evento climático que multiplica por cuatro la llegada de
> solicitudes de servicio, el sistema sigue aceptándolas en tiempo interactivo y
> completa las sagas sin acumular trabajo pendiente.

**Criterios de aceptación** (los cuatro deben cumplirse en la etapa de pico):

| # | Criterio | Umbral | Medido | Veredicto |
|---|---|---|---|---|
| 1.1 | Latencia de aceptación p95 | < 500 ms | ⟨…⟩ | ⟨…⟩ |
| 1.2 | Latencia de aceptación p99 | < 1000 ms | ⟨…⟩ | ⟨…⟩ |
| 1.3 | Tasa de saturación | < 1 % | ⟨…⟩ | ⟨…⟩ |
| 1.4 | Ritmo logrado respecto al objetivo | ≥ 90 % | ⟨…⟩ | ⟨…⟩ |

**Veredicto: ⟨SE CUMPLE / NO SE CUMPLE⟩.**

**Sustentación técnica** ⟨a redactar con los datos; el argumento es este⟩: la
aceptación se mantiene en ⟨…⟩ ms p95 al cuadruplicar la carga porque la petición
HTTP solo hace dos cosas —crear el trabajo preliminar en su propia base y publicar
un comando—, y ninguna de las dos depende de los otros contextos. El trabajo
pesado se absorbe en el tópico, no en el hilo de la petición. La latencia extremo
a extremo sí crece (de ⟨…⟩ s a ⟨…⟩ s p95): esa es la cola de los consumidores,
y es la variable que se ataca con réplicas. La comparación de una contra dos
réplicas (§2.1) muestra ⟨…⟩, lo que confirma que la táctica de escalado
horizontal por suscripción `Shared` funciona sin cambios de código.

### Hipótesis 2 — Disponibilidad

> **Enunciado.** Si Apache Pulsar se cae con sagas en tránsito, ninguna se pierde:
> al restablecer el broker las sagas retenidas avanzan solas hasta un estado final,
> y mientras tanto el Saga Log sigue consultable.

**Criterios de aceptación:**

| # | Criterio | Umbral | Medido `pausa` | Medido `caida` | Veredicto |
|---|---|---|---|---|---|
| 2.1 | Sagas retenidas recuperadas automáticamente | 100 % | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 2.2 | Saga Log consultable durante la caída | HTTP 200 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 2.3 | Tiempo de recuperación total | < 120 s | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
| 2.4 | Ninguna saga retenida termina `FALLIDA` | 0 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |

**Veredicto anticipado: NO SE CUMPLE en su forma fuerte.** ⚠️ Esta es una
**predicción derivada de la lectura del código**, no un resultado medido;
confírmela o refútela con la corrida antes de sustentarla.

**Sustentación técnica de la predicción.** Hay dos mecanismos independientes que
impiden la recuperación total, y el experimento los separa a propósito:

1. En modo `caida`, el broker arranca con `rm -rf /pulsar/data/*`
   (`docker-compose.yml`), porque un bookie standalone que cambia de dirección no
   puede recuperar sus ledgers anteriores. Los mensajes en tránsito dejan de
   existir. Como no hay Outbox, nadie los vuelve a emitir: la recuperación
   esperada es **0 %**.
2. En modo `pausa` los ledgers sobreviven, así que los comandos ya publicados sí
   deberían entregarse al reanudar. Pero las sagas cuyo orquestador estaba
   intentando publicar el comando siguiente durante el congelamiento quedan
   detenidas de todos modos, porque el consumidor de eventos de saga confirma el
   mensaje aun cuando el manejo lanza excepción
   (`consumidor_eventos_saga_pulsar.py:82-87`). La recuperación esperada es
   **parcial**, y su porcentaje depende de cuántas sagas estaban en esa ventana.

**Lo que sí se sostiene**, y conviene decirlo con la misma claridad: el criterio
2.2 se cumple. La lectura del Saga Log solo toca PostgreSQL, así que durante toda
la caída el sistema siguió respondiendo qué había pasado con cada transacción. La
caída del broker degrada la capacidad de *avanzar* sagas, no la de *auditarlas* —
ese es precisamente el valor de haber persistido el log fuera del bus.

**Correcciones que llevarían la hipótesis a cumplirse**, en orden de costo:

| Corrección | Qué resuelve | Esfuerzo |
|---|---|---|
| `negative_acknowledge` ante fallas técnicas en el consumidor de eventos de saga | Redelivery del evento cuyo comando no se pudo publicar | Bajo |
| Patrón **Outbox** en los cuatro servicios | Entrega garantizada aunque el broker caiga tras el commit | Medio |
| *Reaper* que retome sagas no finales al arrancar | Recuperación aunque el mensaje se haya perdido del todo | Medio |
| Clúster de Pulsar con 3 bookies y volumen persistente | Elimina la pérdida de ledgers del modo `caida` | Infraestructura |

### Hipótesis 3 — Consistencia transaccional

> **Enunciado.** Con sagas concurrentes fallando en puntos distintos después de la
> retención del pago, la discrepancia entre el dinero registrado y el Saga Log es
> exactamente `0`: no hay dinero fantasma ni dinero perdido.

**Criterios de aceptación:**

| # | Criterio | Umbral | Medido | Veredicto |
|---|---|---|---|---|
| 3.1 | Discrepancia bruta (Σ \|desvío\| por saga) | = 0 | ⟨…⟩ | ⟨…⟩ |
| 3.2 | Sagas con dinero fantasma o perdido | 0 | ⟨…⟩ | ⟨…⟩ |
| 3.3 | Acreditaciones duplicadas | 0 | ⟨…⟩ | ⟨…⟩ |
| 3.4 | Sagas en estado `FALLIDA` | 0 | ⟨…⟩ | ⟨…⟩ |
| 3.5 | Movimiento del saldo = suma de acreditaciones | iguales | ⟨…⟩ | ⟨…⟩ |

**Veredicto: ⟨SE CUMPLE / NO SE CUMPLE⟩.**

**Sustentación técnica** ⟨a redactar con los datos; el argumento es este⟩: la
identidad `cobrado = acreditado + custodia` se sostiene saga por saga, con ⟨…⟩
sagas concurrentes fallando en tres puntos distintos. Tres mecanismos lo
producen, y cada uno es verificable por separado:

- **Unidad de Trabajo por caso de uso.** En WalletBC el saldo y su movimiento se
  confirman en la misma transacción o no se confirma ninguno, de modo que no
  existe un estado intermedio donde el saldo subió sin dejar rastro auditable.
- **Idempotencia por referencia de saga.** La acreditación se identifica con
  `saga:{saga_id}:acreditacion` y la autorización con `saga:{saga_id}:autorizacion`.
  Un comando reentregado encuentra el movimiento ya hecho y no lo duplica: es el
  criterio 3.3, y está cubierto además por la prueba unitaria
  `test_comando_reentregado_no_acredita_dos_veces`.
- **Compensación encadenada por confirmación.** El reverso del pago solo se da por
  bueno cuando llega `PagoTrabajoRevertidoV1`; si no llega, la saga cae a `FALLIDA`
  y el auditor la marca. Esto convierte una compensación a medias en una alarma en
  lugar de en un descuadre silencioso.

**Sobre `EN_DISPUTA`.** ⟨…⟩ sagas terminaron en disputa y su dinero aparece como
custodia, no como descuadre. Es la decisión de diseño correcta: el servicio ya se
prestó, así que revertir el cobro para "cuadrar" sería regalar el trabajo del
proveedor. Lo que el auditor exige es que **toda** custodia esté respaldada por
una saga `EN_DISPUTA` en el log; custodia sin respaldo sí sería descuadre.

### Resumen ejecutivo de veredictos

| Escenario | Hipótesis | Veredicto | Evidencia principal |
|---|---|---|---|
| 1 — Elasticidad | Acepta y completa 4x la carga base sin degradarse | ⟨…⟩ | Aceptación p95 ⟨…⟩ ms, saturación ⟨…⟩ % |
| 2 — Disponibilidad | Ninguna saga se pierde ante la caída del broker | ⟨NO SE CUMPLE en forma fuerte⟩ | Recuperación ⟨…⟩ %; Saga Log consultable (HTTP 200) |
| 3 — Consistencia | Discrepancia de dinero estrictamente 0 | ⟨…⟩ | Discrepancia bruta ⟨…⟩ sobre ⟨…⟩ sagas concurrentes |

---

## 5. Guion del video de sustentación (≤ 45 min)

Presupuesto sugerido para los dos bloques pedidos. El resto del tiempo queda para
la arquitectura general, el patrón Saga y el BFF.

| Bloque | Duración |
|---|---|
| A — WalletBC en la saga | 12 min |
| B — Experimentos, métricas y validación de hipótesis | 15 min |

> Convención: **[pantalla]** indica qué mostrar; el resto es lo que se dice.
> Los ⟨…⟩ se reemplazan con sus números reales al grabar.

---

### Bloque A — El Bounded Context de Wallet en la Saga (12 min)

#### A.1 Por qué Wallet es el último paso y por qué eso importa (2 min)

**[pantalla: diagrama de los 5 pasos de la saga]**

«La Saga de Activación de Servicio tiene cinco pasos: creamos el trabajo
preliminar, PagosBC autoriza el pago, OperacionesBC asigna el proveedor,
OperacionesBC reporta que el trabajo se ejecutó en campo, y finalmente WalletBC
acredita la liquidación al proveedor.

Wallet es el último, y esa posición define todo su diseño. Los cuatro primeros
pasos son reversibles: si algo falla, compensamos en orden inverso. El quinto
**no se compensa**, y no es un descuido: para cuando llegamos a acreditarle al
proveedor, el trabajo físico ya se prestó. El cliente ya tiene el baño reparado.
Revertir el pago en ese punto sería quitarle al proveedor el dinero de un
servicio que sí entregó.

Entonces, cuando la acreditación falla de forma definitiva, el trabajo no se
cancela ni se revierte: pasa a `EN_DISPUTA`, y Operaciones lo resuelve a mano.
Perdemos automatismo a cambio de no perder dinero de nadie. Esta decisión va a
reaparecer en el escenario de consistencia, donde `EN_DISPUTA` cuenta como
*custodia declarada* y no como descuadre.»

#### A.2 El contrato: cómo entra y cómo responde (2 min)

**[pantalla: `consumidor_comandos_wallet_pulsar.py`, líneas 12-14 y 97-143]**

«WalletBC no expone un endpoint para la saga: participa **solo por mensajería**.
Consume el comando `AcreditarProveedorV1` del tópico `comandos-wallet`, con
suscripción `Shared`, y responde en `eventos-wallet` con uno de dos eventos:
`WalletAcreditadaV1` si acreditó, o `AcreditacionFallidaV1` si agotó sus
reintentos.

Cada mensaje lleva el `saga_id` y el `command_type` en las **propiedades** de
Pulsar, no solo en el cuerpo, para poder filtrar sin deserializar. La clave de
partición es el `trabajo_id`, lo que garantiza que todos los mensajes de una misma
saga se procesen en orden aunque haya varias réplicas.

Fíjense en el detalle del *ack* —línea 89 y el comentario de la clase—: WalletBC
confirma el mensaje en **los dos** desenlaces, incluso cuando la acreditación
falló. La razón es que para cuando emite `AcreditacionFallidaV1` ya agotó su
política de reintentos; reentregar el comando no cambiaría el resultado. El fallo
continúa su curso en el orquestador, que es quien decide abrir la disputa.»

#### A.3 La regla de dominio: `acreditar_liquidacion` (2 min)

**[pantalla: `app/dominio/billetera/billetera.py`, método `acreditar_liquidacion`]**

«Acá está la parte que sí es dominio puro, sin FastAPI ni Pulsar de por medio.

WalletBC tiene dos formas de acreditar y **no** son la misma operación. El
`acreditar` administrativo es un ajuste contable. El `acreditar_liquidacion` es el
pago de un trabajo, y exige que la billetera esté **activa**: una billetera
suspendida no puede recibir la liquidación mientras Operaciones no resuelva por
qué está suspendida.

Y miren lo que hace cuando rechaza: antes de lanzar el error, emite el evento de
dominio `AcreditacionRechazada`. El rechazo no toca el saldo, pero sí queda
anunciado, porque el hecho de que una liquidación fue rechazada es información de
negocio, no un detalle técnico que se pierde en un try/except.

Esa distinción entre las dos operaciones es lo que permite que el orquestador no
sepa nada de billeteras. Él solo pide "acredítale al proveedor"; qué significa eso
y bajo qué condiciones es conocimiento que vive acá.»

#### A.4 Idempotencia y Unidad de Trabajo (2 min)

**[pantalla: `procesar_comando_saga.py`, método `referencia` y el bloque `intento`]**

«Dos garantías que sostienen el escenario de consistencia.

La primera es **idempotencia por referencia de saga**. Cada acreditación se
identifica con la cadena `saga:{saga_id}:acreditacion`. Antes de mover un peso, el
procesador pregunta si la billetera ya tiene un movimiento con esa referencia; si
lo tiene, devuelve la billetera sin tocar el saldo. Un comando reentregado por
Pulsar —que en una arquitectura *at-least-once* va a pasar— no duplica el pago.

La segunda es la **Unidad de Trabajo**. Todo el intento ocurre dentro de
`with self._fabrica_uow() as uow:`, y el saldo y su movimiento se confirman
juntos con `uow.confirmar()` o no se confirma ninguno. No existe un estado
intermedio donde el saldo subió sin que quedara el movimiento que lo explica. Los
eventos de dominio se despachan **después** del commit, nunca dentro.»

**[pantalla: `tests/test_unidad_de_trabajo_y_saga.py`, lista de tests]**

«Y esto no es una afirmación de diapositiva: está cubierto por pruebas.
`test_comando_reentregado_no_acredita_dos_veces`,
`test_confirmar_persiste_saldo_y_movimiento_juntos`,
`test_excepcion_a_mitad_del_caso_de_uso_revierte_la_transaccion`.»

#### A.5 Reintentos: distinguir lo transitorio de lo permanente (2 min)

**[pantalla: `ERRORES_PERMANENTES` y `PoliticaDeReintentos`]**

«WalletBC es quien decide cuántas veces vale la pena insistir, porque es el único
que sabe qué significa cada fallo.

La política son tres intentos con backoff exponencial: espera 0,5 segundos, luego
1, luego 2. Eso sirve para un fallo **transitorio** —una billetera bloqueada que
se reactiva, una caída puntual de la base—: darle tiempo al recurso a recuperarse.

Pero hay fallos que no cambian por esperar: que el proveedor no tenga billetera,
que la moneda no corresponda, que el monto sea inválido. Esos están en
`ERRORES_PERMANENTES` y salen de inmediato, sin reintentar. Insistir ahí solo
retrasaría la disputa, que es lo que de verdad hay que abrir.

Tenemos una prueba bonita para esto:
`test_billetera_reactivada_entre_reintentos_termina_acreditando`. Simula que la
billetera se reactiva entre el intento uno y el dos, y verifica que la saga
termina bien. Esa es exactamente la situación para la que existe el backoff.»

#### A.6 Demostración en vivo (2 min)

**[pantalla: terminal]**

```bash
# Camino feliz: la acreditación cierra la saga
python3 -m scripts.probar_saga_orquestada --modo exito
```

«Miren el paso 5: `ACREDITAR_PROVEEDOR`, servicio `wallet-service`, estado
`EXITOSO`, y la saga queda `COMPLETADA_EXITOSA`.»

```bash
# Acreditación fallida: se agotan los reintentos y se abre la disputa
python3 -m scripts.probar_saga_orquestada --modo disputa-wallet
```

«Acá WalletBC agotó sus tres intentos y emitió `AcreditacionFallidaV1`. Fíjense en
qué **no** pasó: el pago no se revirtió y el trabajo no se canceló. La saga
terminó `EN_DISPUTA` con el paso registrado como
`ABRIR_DISPUTA_REVISION_MANUAL`.»

**[pantalla: `GET /wallet/billeteras?proveedor_id=prov-hda-expert-01` y sus movimientos]**

«Y del lado de la billetera se ve el movimiento con su `referencia_externa`:
`saga:...:acreditacion`. Esa referencia es la que después usa el auditor del
escenario 3 para cruzar el dinero contra el Saga Log.»

---

### Bloque B — Experimentos, métricas y validación de hipótesis (15 min)

#### B.1 Cómo medimos y por qué así (2 min)

**[pantalla: tabla de los 3 escenarios]**

«Automatizamos tres experimentos, uno por escenario de calidad. Los tres miden el
sistema **desde afuera, por HTTP**, porque esa es la vista que tiene un cliente
real, y los tres imprimen un veredicto explícito por hipótesis con umbrales
fijados de antemano.

Antes de los números, tres decisiones de medición que condicionan cómo se leen.

La primera: **separamos dos latencias**. El `POST` que inicia la saga responde
`202` apenas crea el trabajo preliminar y publica el comando de pago; todo lo
demás pasa después, por Pulsar. Entonces medimos por un lado la *aceptación* —lo
que espera el partner— y por otro la *saga completa*, que calculamos con las
marcas de tiempo del propio Saga Log para que el intervalo de sondeo del script no
la contamine. Confundir las dos es el error clásico al medir una arquitectura
asíncrona: reportaríamos 20 milisegundos de latencia cuando la transacción real
tarda segundos.

La segunda: en el escenario de dinero reportamos la discrepancia **bruta**, no la
neta. Lo descubrimos probando el auditor contra un stub con errores inyectados a
propósito: un peso perdido y un peso fantasma del mismo tamaño se cancelan en el
agregado, y el total daba cero con cuatro sagas rotas adentro. La cifra que vale
es la suma de los desvíos en valor absoluto.

La tercera: cada saga lleva un monto distinto, para que un cruce entre
acreditaciones se delate por monto además de por referencia.»

#### B.2 Escenario 1 — Elasticidad (4 min)

**[pantalla: tabla §2.1 y la salida del script]**

«La hipótesis: ante un pico de cuatro veces la carga base —piensen en una
granizada que dispara los siniestros— el sistema sigue aceptando en tiempo
interactivo y termina las sagas sin acumular pendientes.

Subimos la carga por etapas, de ⟨2⟩ a ⟨8⟩ sagas por segundo, sin pausa entre
etapas porque un pico real no hace pausas.

Los resultados: la aceptación p95 pasó de ⟨…⟩ a ⟨…⟩ milisegundos, es decir un
factor de ⟨…⟩. La saga completa p95 pasó de ⟨…⟩ a ⟨…⟩ segundos. Y la saturación
—la fracción de sagas que, agotado el drenaje, siguen abiertas— fue de ⟨…⟩ %.

La lectura arquitectónica: la aceptación casi no se mueve porque la petición HTTP
solo hace dos cosas, ambas locales: escribir el trabajo preliminar en su propia
base y publicar un comando. No llama a Pagos, ni a Operaciones, ni a Wallet. El
trabajo pesado se absorbe en el tópico, no en el hilo de la petición. Lo que sí
crece es la latencia extremo a extremo, y eso es la cola de los consumidores.

Y la cola de los consumidores tiene una respuesta directa: agregar réplicas.
**[pantalla: tabla de 1 vs 2 réplicas]** Con dos instancias del orquestador
compartiendo la misma suscripción `Shared`, ⟨…⟩. Sin una sola línea de cambio en
el código: Pulsar reparte los comandos entre las réplicas.

**Veredicto: ⟨se cumple / no se cumple⟩**, porque ⟨…⟩.»

#### B.3 Escenario 2 — Disponibilidad (5 min)

**[pantalla: tabla §2.2]**

«Este es el escenario más interesante, porque el resultado no es el que
esperábamos y eso lo vuelve más útil.

La hipótesis: si Pulsar se cae con sagas en tránsito, ninguna se pierde; al
restablecerlo avanzan solas.

Derribamos el broker de dos formas distintas a propósito, y la diferencia entre
ellas *es* el resultado. En modo `pausa` congelamos el contenedor: los datos del
broker sobreviven, que es lo que se parece a una partición de red. En modo `caida`
lo matamos y lo volvemos a levantar, y ahí hay que ser honestos con algo de
nuestro propio despliegue: nuestro Pulsar arranca en standalone borrando su
directorio de datos, porque un bookie que cambia de dirección no puede recuperar
sus ledgers. Es una decisión consciente para la POC, y tiene una consecuencia
medible: los mensajes en tránsito dejan de existir.

Resultados: en modo `pausa` se recuperaron ⟨…⟩ de ⟨…⟩ sagas retenidas. En modo
`caida`, ⟨…⟩.

**Veredicto: la hipótesis no se cumple en su forma fuerte**, y podemos explicar
exactamente por qué, que es lo que hace útil al experimento. Hay dos causas
independientes.

La primera: **no tenemos Outbox**. Publicamos los eventos después de confirmar la
transacción; si el broker cae en esa ventana, el evento se pierde y nadie lo
reintenta.

La segunda es más sutil y la encontramos leyendo el código para diseñar el
experimento. **[pantalla: `consumidor_eventos_saga_pulsar.py:82-87`]** Nuestro
consumidor de eventos de saga confirma el mensaje **aunque el manejo falle**. Si
el orquestador recibe un evento y no logra publicar el comando siguiente porque el
broker está caído, ese evento queda confirmado y se pierde. La saga se detiene en
ese paso aunque el broker vuelva.

Ahora, algo **sí** se cumplió, y es importante: **[pantalla: los dos códigos HTTP
de la sonda]** durante toda la caída el Saga Log siguió consultable, HTTP 200.
Iniciar una saga nueva sí falló, con HTTP ⟨…⟩. Esa diferencia es el radio de
impacto real: leer el Saga Log solo toca PostgreSQL; iniciar una saga necesita
publicar en Pulsar. La caída del broker degrada nuestra capacidad de **avanzar**
transacciones, no la de **auditarlas**. Ese es justamente el valor de haber
persistido el Saga Log fuera del bus.

Y sabemos qué hay que hacer, en orden de costo: cambiar ese `acknowledge` por
`negative_acknowledge` ante fallas técnicas —corrección de una línea que
recuperaría el modo `pausa`—, implementar Outbox, agregar un proceso que retome
las sagas no finales al arrancar, y en producción usar un clúster de Pulsar con
tres bookies en vez de un standalone.

Una acotación de validez que corresponde hacer: **Pulsar standalone no es Pulsar
en producción**. Un clúster real con réplicas sobrevive a la caída de un broker
sin perder ledgers. Lo que medimos aplica a este despliegue.»

#### B.4 Escenario 3 — Consistencia (4 min)

**[pantalla: tabla §2.3]**

«La hipótesis: con sagas concurrentes fallando en puntos distintos después de la
retención del pago, la discrepancia de dinero es exactamente cero.

Lanzamos ⟨20⟩ sagas en paralelo, sorteando en cada una dónde falla: en
Operaciones, en la ejecución en campo, en Wallet, o que no falle. Después
auditamos cruzando **tres bases de datos distintas**: el Saga Log en
GestionDeTrabajos, el pago en PagosBC y el movimiento en WalletBC, cotejados por
las referencias `saga:{id}:autorizacion` y `saga:{id}:acreditacion`.

La identidad que verificamos es: **cobrado = acreditado + custodia**.

Y acá está la parte conceptual que quiero destacar: `EN_DISPUTA` **no** es un
descuadre, es custodia declarada. El servicio ya se prestó, el cobro se sostiene, y
el Saga Log deja constancia de que Operaciones debe resolverlo. Un sistema que
"cuadrara" revirtiendo el cobro de un servicio ya prestado estaría regalando el
trabajo del proveedor a cambio de una métrica bonita. Lo que sí sería descuadre es
custodia **sin** una saga que la respalde, y eso es lo que el auditor verifica.

Resultados: ⟨…⟩ sagas exitosas, ⟨…⟩ compensadas, ⟨…⟩ en disputa, cero fallidas.
Discrepancia bruta: ⟨…⟩. Cero acreditaciones duplicadas. Y el movimiento del saldo
de la billetera coincide exactamente con la suma de las acreditaciones.

**Veredicto: ⟨se cumple⟩**, y se sostiene en tres mecanismos verificables por
separado: la Unidad de Trabajo, que confirma saldo y movimiento juntos; la
idempotencia por referencia de saga, que hace inofensiva una reentrega; y la
compensación encadenada por confirmación, que solo da por buena una reversión
cuando llega el evento que la confirma —y si no llega, la saga cae a `FALLIDA` y
el auditor la marca, en vez de dejar un descuadre silencioso.»

#### B.5 Cierre: qué aprendimos (2 min)

**[pantalla: tabla resumen de veredictos, §4]**

«Cerrando los tres escenarios.

Elasticidad: ⟨…⟩. La arquitectura asíncrona hace que la aceptación sea barata y
que el costo del pico se absorba en el tópico, donde se puede atacar con réplicas.

Disponibilidad: no se cumple en su forma fuerte, y sabemos exactamente por qué y
qué cuesta arreglarlo. Sí se cumple la parte de observabilidad: el Saga Log
sobrevive a la caída del bus.

Consistencia: ⟨…⟩, con cero descuadre bruto bajo fallo concurrente.

Y una reflexión sobre el método: dos de los hallazgos más valiosos no salieron de
los números sino de **diseñar los experimentos**. El `ack` que se traga los
errores lo encontramos leyendo el consumidor para saber qué debíamos medir; y lo
de la discrepancia neta contra la bruta lo encontramos probando el auditor contra
un stub con errores inyectados a propósito, y viendo que reportaba cero con cuatro
sagas rotas. Un experimento que solo confirma lo que uno ya creía no estaba bien
diseñado.»

---

## 6. Checklist antes de grabar

- [ ] Correr los tres experimentos tres veces y llenar todos los ⟨…⟩ con la mediana.
- [ ] Confirmar o refutar la predicción de la Hipótesis 2 con los datos reales.
- [ ] Guardar los CSV de las corridas como evidencia.
- [ ] Tener a mano una saga de cada desenlace para mostrar su `GET /sagas/{id}`.
- [ ] Verificar que el stack esté sano justo antes de grabar: `curl http://localhost/salud`.
- [ ] Si se graba contra la EC2: confirmar que Pulsar y las bases estén arriba
      (hoy no tienen `restart: unless-stopped`, así que un reinicio de la VM deja
      las APIs corriendo sin broker ni bases).
