# Sustentación — Escenarios de Calidad sobre la Saga

## Proyecto: Hogar de los Alpes

Documento de sustentación de los tres escenarios de calidad evaluados sobre la
**Saga de Activación de Servicio**: elasticidad ante picos, disponibilidad ante la
caída del broker y consistencia transaccional bajo fallo concurrente.

Todas las cifras de este documento provienen de corridas reales ejecutadas el
**2026-09-21** con los scripts de `gestion-trabajos-service/scripts/`. Los CSV de
cada corrida quedan como evidencia.

---

## 1. Metodología

### 1.1 Ambiente de ejecución

| Elemento | Valor |
|---|---|
| Infraestructura | Portátil con Docker Desktop (no EC2) |
| CPU disponible para Docker | 16 vCPU |
| Memoria disponible para Docker | 7,72 GiB |
| Versión de Docker | 29.7.2 |
| Consumo del stack en reposo | ~3,0 GiB (Pulsar 2,40 GiB; cada API 42–111 MiB; cada base 23–67 MiB) |
| Servicios desplegados | 5 servicios + 4 PostgreSQL + Pulsar standalone + gateway Nginx |
| Fecha de la corrida | 2026-09-21 |

> **Amenaza a la validez.** Estas cifras son de un portátil, no de la `t3.large`
> de referencia. Los valores absolutos de latencia y el punto de saturación
> cambiarán en EC2; lo que se traslada es la **forma** de las curvas y las
> conclusiones cualitativas. Los experimentos se corren con el mismo comando en
> ambos ambientes.

Los experimentos se ejecutan desde la propia máquina que hospeda el stack: las
APIs directas, las bases y Pulsar están ligadas a `127.0.0.1` y solo el gateway
escucha en el puerto 80. Se usa `127.0.0.1` y no `localhost` porque, al no haber
listener IPv6, un cliente que resuelva `localhost` intenta `::1` primero y pierde
unos dos segundos por petición.

### 1.2 Instrumentación

Los tres experimentos están automatizados y solo usan la biblioteca estándar de
Python. Miden el sistema **desde afuera, por HTTP**, que es la vista de un cliente
real, e imprimen un veredicto explícito por hipótesis contra umbrales fijados de
antemano.

```bash
cd gestion-trabajos-service
python3 -m scripts.carga_elasticidad_sagas --csv                             # Escenario 1 (nominal)
python3 -m scripts.carga_elasticidad_sagas --base 10 --duracion 12 --hilos 32 --csv   # Escenario 1 (estrés)
python3 -m scripts.auditoria_consistencia_sagas --num 20 --csv               # Escenario 3
python3 -m scripts.prueba_disponibilidad_pulsar --modo pausa --csv           # Escenario 2a
python3 -m scripts.prueba_disponibilidad_pulsar --modo caida --num 20 --csv  # Escenario 2b
python3 -m scripts.auditoria_consistencia_sagas --solo-auditar --limite 21   # impacto del corte
```

El protocolo completo está en
[`docs/semana-7/experimentos-escenarios-saga.md`](docs/semana-7/experimentos-escenarios-saga.md).

**Tres decisiones de medición que condicionan la lectura:**

1. **Se separan dos latencias.** `POST /sagas/activar-servicio` responde `202`
   apenas crea el trabajo preliminar y publica el comando de pago; el resto ocurre
   por Pulsar. La *latencia de aceptación* es lo que percibe el partner; la
   *latencia extremo a extremo* es la transacción completa, calculada con las
   marcas de tiempo del propio Saga Log para que el sondeo del script no la
   contamine. Confundirlas es el error clásico al medir una arquitectura asíncrona.
2. **Se reporta la discrepancia bruta, no la neta.** Un peso perdido y un peso
   fantasma del mismo tamaño se cancelan en el agregado. Esto no es teórico: al
   validar el auditor contra un stub con errores inyectados, la discrepancia neta
   dio `0.00` con cuatro sagas rotas adentro. La cifra que sostiene la hipótesis es
   la suma de desvíos **en valor absoluto**.
3. **Cada saga lleva un monto distinto**, para que un cruce entre acreditaciones se
   delate por monto además de por referencia.

### 1.3 Repetición

**Limitación declarada:** se ejecutó **una corrida por configuración**, no tres con
mediana. Las conclusiones cualitativas son robustas (los efectos son de uno a dos
órdenes de magnitud), pero los valores exactos de percentiles deben tomarse como
indicativos. Antes de grabar la sustentación conviene repetir cada configuración
tres veces y reportar la mediana.

El escenario 1 calienta con una saga completa antes de medir: la primera saga de un
Pulsar recién arrancado paga la creación de los seis tópicos y sus suscripciones.

---

## 2. Resultados cuantitativos

### 2.1 Escenario 1 — Elasticidad ante picos de demanda

#### Corrida A — carga nominal (línea base 2 sagas/s, 20 s por etapa, 400 sagas)

| Etapa | Objetivo (sagas/s) | Logrado | req/s | Acept. prom. (ms) | p50 | p95 | p99 | Saga p50 (s) | p95 | p99 | Saturación |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1x | 2,00 | 2,00 | 2,00 | 53,5 | 55,2 | 68,4 | 72,2 | 0,14 | 0,15 | 0,18 | 0/40 (0 %) |
| 2x | 4,00 | 4,00 | 4,00 | 47,1 | 45,0 | 62,3 | 69,6 | 0,13 | 0,15 | 0,17 | 0/80 (0 %) |
| 3x | 6,00 | 6,00 | 6,00 | 47,3 | 44,6 | 65,7 | 70,8 | 0,14 | 0,16 | 0,18 | 0/120 (0 %) |
| **4x (pico)** | **8,00** | **8,00** | **8,00** | **56,0** | **52,8** | **73,4** | **100,2** | **0,15** | **0,20** | **0,31** | **0/160 (0 %)** |

- Sagas iniciadas: **400**. Desenlace: **400 `COMPLETADA_EXITOSA`**, 0 fallos.
- Degradación 1x → 4x: aceptación p95 **68 → 73 ms (×1,1)**; saga completa p95
  **0,15 → 0,20 s (×1,3)**.
- Ritmo en el pico: **8,00 / 8,00 sagas/s (100 % del objetivo)**.

#### Corrida B — estrés (línea base 10 sagas/s, 12 s por etapa, 1200 sagas)

La corrida A no encontró el límite del sistema, así que se repitió con cinco veces
la línea base para caracterizar el punto de quiebre.

| Etapa | Objetivo (sagas/s) | Logrado | Acept. prom. (ms) | p50 | p95 | p99 | Saga p50 (s) | p95 | p99 | Saturación |
|---|---|---|---|---|---|---|---|---|---|---|
| 1x | 10,00 | 10,00 | 60,5 | 58,1 | 80,0 | 103,8 | 0,17 | 0,21 | 0,26 | 0/120 (0 %) |
| 2x | 20,00 | 19,96 | 166,0 | 136,3 | 353,5 | 448,6 | 10,87 | 32,45 | 32,52 | 0/240 (0 %) |
| 3x | 30,00 | 28,54 | 630,5 | 489,8 | 1203,5 | 1808,5 | 35,40 | 39,29 | 39,81 | 0/360 (0 %) |
| **4x (pico)** | **40,00** | **30,46** | **994,9** | **950,5** | **1571,9** | **2056,4** | **47,68** | **56,75** | **57,55** | **0/480 (0 %)** |

- Sagas iniciadas: **1200**. Desenlace: **1200 `COMPLETADA_EXITOSA`**, 0 fallos.
- Degradación 1x → 4x: aceptación p95 **80 → 1572 ms (×19,6)**; saga completa p95
  **0,21 → 56,75 s (×265,5)**.
- Ritmo en el pico: **30,46 / 40,00 sagas/s (76 % del objetivo)** → techo de
  absorción ≈ **30 sagas/s** en este ambiente.
- **La rodilla está entre 10 y 20 sagas/s:** la latencia extremo a extremo salta de
  0,21 s a 32,45 s p95 mientras la aceptación sigue bajo el umbral (353 ms).

> **Dato central:** la saturación fue **0 % en las ocho etapas de ambas corridas**.
> Ni una sola de las 1600 sagas se perdió o quedó abierta. El sistema **encola**
> bajo presión, no descarta: el límite que se alcanza es de *latencia*, no de
> *corrección*.

#### Comparación de escalado horizontal (1 vs. 2 réplicas del orquestador)

Misma carga de la corrida B, con `gestion-trabajos-2` activo (perfil
`escalabilidad`), compartiendo la suscripción `Shared` y la misma base.

| Etapa | Ritmo logrado 1 réplica | 2 réplicas | Acept. p95 1 rép. | 2 rép. | Saga p95 1 rép. | 2 rép. |
|---|---|---|---|---|---|---|
| 1x (10/s) | 10,00 | 10,00 | 80,0 ms | 82,4 ms | 0,21 s | 0,65 s |
| 2x (20/s) | 19,96 | 19,99 | 353,5 ms | 90,2 ms | 32,45 s | **22,36 s** |
| 3x (30/s) | 28,54 | 27,18 | 1203,5 ms | 1650,3 ms | 39,29 s | 87,41 s |
| 4x (40/s) | **30,46** | **27,66** | 1571,9 ms | 1750,9 ms | 56,75 s | **101,00 s** |

**Reparto de trabajo medido en los logs:**

| Métrica | Réplica 1 | Réplica 2 |
|---|---|---|
| Eventos de saga procesados | 2019 (72 %) | 785 (28 %) |
| Sagas iniciadas por HTTP | todas | **0** |

**La segunda réplica no mejoró el rendimiento; lo empeoró en el pico** (27,66 vs.
30,46 sagas/s; saga p95 101,0 s vs. 56,8 s). Solo ayudó en la etapa 2x. Dos causas
se combinan, y ambas son hallazgos aprovechables:

1. **El gateway no balancea.** `nginx.conf` enruta `/trabajos` a un único upstream,
   así que las 1200 sagas se iniciaron en la réplica 1. La suscripción `Shared`
   reparte el consumo de *eventos* (72/28), pero no el trabajo que entra por HTTP.
   La táctica de escalado horizontal del escenario #4 original aplica a comandos
   que llegan **por Pulsar** (`comandos-trabajo`), no a sagas iniciadas por REST.
2. **El cuello de botella no es el orquestador.** Aun repartiendo el 28 % de los
   eventos, el throughput no subió: el límite está en el broker standalone y en la
   contención de escritura sobre `postgres-trabajos`, que ambas réplicas comparten
   y donde cada paso de cada saga hace varias escrituras en el Saga Log. Agregar
   una réplica añade contención sin añadir capacidad donde falta.

### 2.2 Escenario 2 — Disponibilidad ante la caída de Apache Pulsar

| Modo | Qué hace | Ledgers | Qué representa |
|---|---|---|---|
| `pausa` | `docker pause` | se conservan | Partición de red o pausa de GC larga |
| `caida` | `docker compose kill` + `up -d` | se borran | Reinicio del standalone con datos limpios |

| Métrica | `pausa` | `caida` |
|---|---|---|
| Sagas puestas en tránsito | 12 | 20 |
| Cerradas antes de la caída | 3 | 3 |
| **Retenidas por la caída** | **9** | **17** |
| **Recuperadas automáticamente** | **9/9 (100 %)** | **2/17 (12 %)** |
| No recuperadas | 0 | 15 |
| Tiempo hasta broker `healthy` | 14,4 s | 10,4 s |
| Recuperación de sagas p50 / p95 / máx | 2,0 / 2,0 / 2,0 s | 12,2 / 12,2 / 12,2 s |
| **Recuperación total** (restablecer → última saga) | **16,4 s** | 22,5 s (solo las 2 recuperadas) |
| Leer el Saga Log durante la caída | **HTTP 200** | **HTTP 200** |
| Iniciar una saga durante la caída | timeout | timeout |

**Dónde quedaron detenidas las 15 no recuperadas del modo `caida`:** las quince en
`5:ACREDITAR_PROVEEDOR`. El comando `AcreditarProveedorV1` ya había sido publicado
y se fue con los ledgers borrados; WalletBC nunca lo recibió y nadie lo reemitió.

**Impacto en dinero del corte duro** (auditoría de las 21 sagas más recientes):

| Métrica | Valor |
|---|---|
| Sagas sin estado final tras el corte | 16 |
| Cobrado al cliente | 4 000 190 COP |
| Acreditado al proveedor | 1 200 017 COP |
| En custodia declarada (`EN_DISPUTA`) | 0 COP |
| **Discrepancia bruta atribuible al corte** | **2 800 173 COP en 14 sagas** |

Un caso merece mención aparte: la saga `13b86d04` quedó `EN_PROCESO` **con el pago
confirmado y la acreditación efectivamente hecha** (desvío 0,00). Lo que se perdió
no fue el dinero sino el evento `WalletAcreditadaV1` de respuesta: el dinero está
bien, el Saga Log no se enteró. Es la ilustración exacta de por qué el log necesita
un mecanismo de reconciliación y no solo de registro.

### 2.3 Escenario 3 — Consistencia transaccional bajo fallo concurrente

| Corrida | Sagas | Exitosas | Compensadas | En disputa | Fallidas | Cobrado | Acreditado | Custodia | Discrep. neta | **Discrep. bruta** |
|---|---|---|---|---|---|---|---|---|---|---|
| A — fallos posteriores al pago (semilla 7) | 20 | 10 | 6 | 4 | **0** | 4 340 142 | 3 100 101 | 1 240 041 | 0,00 | **0,00** |
| B — incluyendo fallo en el pago (semilla 11) | 20 | 3 | 10 | 7 | **0** | 3 100 110 | 930 046 | 2 170 064 | 0,00 | **0,00** |
| C — tras el corte duro del broker | 21 | 5 | 0 | 0 | 0 | 4 000 190 | 1 200 017 | 0 | 2 800 173 | **2 800 173** |

> La corrida C no es un fallo del escenario 3: es la medición del daño del
> escenario 2. Con el broker sano (A y B), la discrepancia es exactamente cero.

**Comprobaciones adicionales del auditor (corridas A y B):**

| Comprobación | A | B |
|---|---|---|
| Movimiento del saldo = suma de acreditaciones | 3 100 101 = 3 100 101 ✔ | 930 046 = 930 046 ✔ |
| Toda acreditación ocurrió exactamente una vez | CUMPLE | CUMPLE |
| Ninguna saga terminó `FALLIDA` | CUMPLE | CUMPLE |
| Sagas con dinero fantasma o perdido | 0 | 0 |

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
que consume contratos REST publicados. La consecuencia se midió: el escenario 2
derribó el broker sin tocar ningún servicio, y durante todo el corte las APIs
siguieron respondiendo `HTTP 200` a las consultas del Saga Log. No hay una llamada
directa entre contextos que pudiera quedar colgada.

**El orquestador no conoce el dominio de los participantes.** Emite comandos y
reacciona a eventos; no sabe qué es un PSP, ni cómo se elige un proveedor, ni qué
reglas tiene una billetera. La prueba práctica: el paso 5 pasó de "acreditar" a
"acreditar solo si la billetera está activa, con reintentos y backoff" sin una sola
línea de cambio en el orquestador.

**El core no conoce partners.** Los 1600 inicios de saga del escenario 1 usaron un
`partner_id` que ni siquiera está registrado (`seguros-bolivar`) y el core no se
inmutó: no lo consulta, porque las condiciones ya vienen resueltas en el comando
canónico.

**Dónde sí hay acoplamiento, y es deliberado:** los cinco pasos y sus
compensaciones están codificados en `OrquestadorSagaTrabajo`. Es el costo aceptado
de orquestar en vez de coreografiar, a cambio de un único lugar donde leer y
cambiar el flujo completo.

**Un límite del desacoplamiento que el experimento sacó a la luz:** el escalado
horizontal es parcial. La suscripción `Shared` reparte el consumo de eventos
(72/28 medido), pero el gateway enruta `/trabajos` a un único upstream, así que
toda saga iniciada por REST nace en la misma instancia. Desacoplar por mensajería
no basta para escalar si la puerta de entrada síncrona no se balancea.

### 3.2 Tolerancia a fallos

**El sistema encola, no descarta.** El hallazgo más contundente del escenario 1:
en 1600 sagas y ocho etapas de carga, con el pico exigiendo 40 sagas/s a un sistema
que absorbe 30, la saturación fue **0 %**. Todas terminaron `COMPLETADA_EXITOSA`,
algunas 57 segundos después. La cola de Pulsar convierte un problema de capacidad
en un problema de latencia, que es infinitamente más manejable que la pérdida de
trabajo.

**Compensación encadenada por confirmación, no por optimismo.** Cada compensación
se pide solo cuando llega el evento que confirma la anterior. Si una confirmación
no llega o llega negativa, la saga termina `FALLIDA` en vez de dar por buena una
reversión que nunca ocurrió. En las 40 sagas del escenario 3 con fallos forzados en
cuatro puntos distintos, **cero terminaron `FALLIDA`**: las 16 compensaciones se
completaron íntegras.

**Lo ya ejecutado no se compensa.** Once sagas terminaron `EN_DISPUTA` entre las
corridas A y B, con 3 410 105 COP en custodia declarada. El auditor no las cuenta
como descuadre, y esa es la decisión correcta: el servicio se prestó, así que
revertir el cobro para "cuadrar" sería regalar el trabajo del proveedor.

**El aislamiento resiste, pero la recuperación depende del modo de fallo.** Ante
una partición temporal (`pausa`) la recuperación fue total y rápida: 9 de 9 sagas
en 2,0 segundos tras restablecer. Ante la pérdida de los ledgers (`caida`), 2 de
17. La diferencia no está en el código de la saga sino en la durabilidad del bus.

**Dos límites conocidos, ahora medidos:**

1. **No hay Outbox.** Los eventos se publican después de confirmar la transacción.
   El modo `caida` le puso precio: 2 800 173 COP cobrados y no liquidados en 14
   sagas.
2. **El consumidor de eventos de saga confirma el mensaje aunque el manejo falle**
   (`consumidor_eventos_saga_pulsar.py:82-87`). El riesgo es real, pero **no se
   materializó** en el modo `pausa`: con el broker congelado el consumidor no
   recibe nada, así que ningún manejador corre y nada se confirma indebidamente.
   La ventana peligrosa es más estrecha de lo previsto — exige un broker
   *parcialmente* disponible — y eso mismo la vuelve difícil de reproducir y fácil
   de subestimar.

**Acotación de validez:** Pulsar standalone no es Pulsar en producción. Un clúster
con tres bookies y volumen persistente no pierde ledgers, así que el resultado del
modo `caida` mide este despliegue, no el patrón.

### 3.3 Observabilidad del Saga Log

El Saga Log (`saga_instancias`, `saga_pasos`) no es un log de depuración: es el
registro de negocio que hace auditable una transacción que no tiene una sola base
donde mirar. Los tres experimentos dependieron de él.

- **Latencia extremo a extremo exacta.** `fecha_actualizacion − fecha_creacion` son
  marcas del servidor. Sin ellas, la latencia de la saga se inferiría del intervalo
  de sondeo, con un error del orden del intervalo mismo — inaceptable cuando la
  medición va de 0,21 s a 56,75 s.
- **Distinguir "lento" de "atascado".** La saturación del escenario 1 y las "sagas
  retenidas" del escenario 2 son la misma consulta. Que la saturación fuera 0 %
  mientras la latencia se multiplicaba por 265 solo se puede afirmar porque el
  estado global es explícito y no se deduce del tiempo transcurrido.
- **Ubicar dónde se cortó la cadena.** El log dijo que las 15 sagas perdidas
  quedaron en `5:ACREDITAR_PROVEEDOR`. Eso convirtió "algunas sagas no volvieron"
  en "se perdió el comando de acreditación", que es un diagnóstico accionable.
- **Cotejar dinero contra intención.** El escenario 3 cruza tres bases distintas
  por las referencias `saga:{id}:autorizacion` y `saga:{id}:acreditacion`. El Saga
  Log es la única fuente que dice cuál *debía* ser el desenlace; PagosBC y WalletBC
  solo saben de su parte. Sin él, la saga `13b86d04` —dinero correcto, log
  desactualizado— sería indistinguible de una pérdida real.

**Superficie de consulta:** `GET /sagas` lista las transacciones recientes con su
estado global; `GET /sagas/{id}` devuelve el detalle paso a paso con comando
enviado, evento recibido, error y marcas de tiempo. Los cuatro estados finales son
un vocabulario cerrado, lo que permitió automatizar el veredicto en vez de leerlo
a ojo.

**Límite actual, ahora cuantificado:** el log registra lo que el orquestador hizo,
pero no lo resucita. Las 16 sagas que quedaron `EN_PROCESO` siguen ahí, visibles y
sin avanzar. La corrección natural es un *reaper* que relea las sagas no finales y
reemita el comando pendiente, apoyándose en la idempotencia que los participantes
ya tienen — y que el escenario 3 demostró que funciona.

---

## 4. Conclusiones sobre las hipótesis

### Hipótesis 1 — Elasticidad

> Ante un evento climático que multiplica por cuatro la llegada de solicitudes, el
> sistema sigue aceptándolas en tiempo interactivo y completa las sagas sin
> acumular trabajo pendiente.

| # | Criterio | Umbral | Corrida A (pico 8/s) | Corrida B (pico 40/s) |
|---|---|---|---|---|
| 1.1 | Aceptación p95 | < 500 ms | **73,4 ms** ✔ | 1571,9 ms ✘ |
| 1.2 | Aceptación p99 | < 1000 ms | **100,2 ms** ✔ | 2056,4 ms ✘ |
| 1.3 | Tasa de saturación | < 1 % | **0 %** ✔ | **0 %** ✔ |
| 1.4 | Ritmo logrado / objetivo | ≥ 90 % | **100 %** ✔ | 76 % ✘ |

## **Veredicto: SE CUMPLE dentro del rango nominal evaluado (hasta 8 sagas/s), con el techo de absorción identificado en ~30 sagas/s.**

**Sustentación técnica.** Al cuadruplicar la carga nominal, la latencia de
aceptación pasó de 68 a 73 ms p95: un factor de 1,1 sobre un aumento de carga de
4×. La razón es arquitectónica: la petición HTTP solo hace dos cosas, ambas
locales —escribir el trabajo preliminar en su propia base y publicar un comando—,
y no llama a Pagos, ni a Operaciones, ni a Wallet. El trabajo pesado se absorbe en
el tópico, no en el hilo de la petición.

La corrida de estrés muestra dónde está el límite y de qué tipo es. Entre 10 y 20
sagas/s la latencia extremo a extremo salta de 0,21 s a 32,45 s p95 mientras la
aceptación sigue bajo umbral: la cola crece en los consumidores, no en la puerta.
A 40 sagas/s el sistema solo absorbe 30,46. **Pero la saturación se mantuvo en 0 %
en las ocho etapas: las 1600 sagas terminaron `COMPLETADA_EXITOSA`.** El límite
alcanzado es de latencia, no de corrección — el sistema encola bajo presión y no
descarta trabajo, que es exactamente el comportamiento que se le pide a una
arquitectura reactiva ante un pico de siniestros.

**Matiz sobre la táctica de escalado.** La hipótesis original suponía que agregar
réplicas del orquestador movería el techo. **No lo hizo**: con dos réplicas el pico
bajó de 30,46 a 27,66 sagas/s. La medición de los logs explica por qué: la réplica
2 procesó el 28 % de los eventos de saga pero **inició 0 sagas por HTTP**, porque
el gateway enruta `/trabajos` a un único upstream. Y aun con ese 28 % repartido el
throughput no subió, lo que sitúa el cuello de botella en el broker standalone y en
la contención sobre `postgres-trabajos`, compartida por ambas réplicas. Para que el
escalado horizontal rinda hay que balancear el gateway y separar el almacenamiento
del Saga Log, no solo agregar contenedores.

### Hipótesis 2 — Disponibilidad

> Si Apache Pulsar se cae con sagas en tránsito, ninguna se pierde: al restablecer
> el broker las sagas retenidas avanzan solas hasta un estado final, y mientras
> tanto el Saga Log sigue consultable.

| # | Criterio | Umbral | `pausa` | `caida` |
|---|---|---|---|---|
| 2.1 | Sagas retenidas recuperadas | 100 % | **9/9 (100 %)** ✔ | 2/17 (12 %) ✘ |
| 2.2 | Saga Log consultable durante la caída | HTTP 200 | **HTTP 200** ✔ | **HTTP 200** ✔ |
| 2.3 | Tiempo de recuperación total | < 120 s | **16,4 s** ✔ | 22,5 s (parcial) ◐ |
| 2.4 | Ninguna saga retenida termina `FALLIDA` | 0 | **0** ✔ | **0** ✔ |

## **Veredicto: SE CUMPLE ante partición temporal; NO SE CUMPLE ante pérdida de los ledgers.**

**Sustentación técnica.** El resultado depende enteramente de si el broker conserva
sus datos, y el experimento separó los dos casos a propósito.

Ante una **partición temporal** (`pausa`, 15 s congelado) la hipótesis se cumple sin
reservas: las 9 sagas retenidas se recuperaron solas, todas en 2,0 segundos tras
restablecer, y ninguna quedó en estado inconsistente. Los comandos publicados
seguían en los ledgers y los consumidores reconectaron por su cuenta. La
recuperación total —desde restablecer hasta la última saga cerrada— fue de 16,4 s,
de los cuales 14,4 s los consumió el propio arranque del broker: la arquitectura
aportó apenas 2 segundos.

Ante la **pérdida de los ledgers** (`caida`) se recuperaron 2 de 17. Las 15
restantes quedaron detenidas en `5:ACREDITAR_PROVEEDOR`: el comando ya publicado se
fue con los datos borrados y no hay Outbox que lo reemita ni reaper que retome la
saga. El costo se cuantificó: **2 800 173 COP cobrados y no liquidados en 14
sagas**. Conviene ser preciso al sustentarlo: la causa es que nuestro Pulsar
standalone arranca con `rm -rf /pulsar/data/*` —decisión consciente de la POC,
porque un bookie que cambia de dirección no puede recuperar sus ledgers— y no un
defecto del patrón Saga.

**Lo que sí se cumple en ambos modos, y es el hallazgo que conviene destacar:** el
criterio 2.2. Durante toda la caída, en los dos modos, el Saga Log respondió
`HTTP 200`. Iniciar una saga nueva sí falló por timeout. Esa asimetría es el radio
de impacto real: leer el Saga Log solo toca PostgreSQL; iniciar una saga necesita
publicar en Pulsar. **La caída del broker degrada la capacidad de *avanzar*
transacciones, no la de *auditarlas*** — que es precisamente el valor de haber
persistido el log fuera del bus.

**Corrección de una predicción previa.** Antes de correr el experimento se predijo,
leyendo el código, que el modo `pausa` recuperaría solo parcialmente, porque el
consumidor de eventos de saga confirma el mensaje aunque el manejo falle
(`consumidor_eventos_saga_pulsar.py:82-87`). **La medición refutó la predicción:**
la recuperación fue del 100 %. La explicación es que con el broker congelado el
consumidor no recibe nada, así que ningún manejador llega a correr y nada se
confirma indebidamente. El riesgo del `ack` en el `except` sigue existiendo, pero
su ventana exige un broker *parcialmente* disponible y es más estrecha de lo que
sugería la lectura del código.

**Correcciones que llevarían la hipótesis a cumplirse también en el modo `caida`:**

| Corrección | Qué resuelve | Esfuerzo |
|---|---|---|
| Clúster de Pulsar con 3 bookies y volumen persistente | Elimina la pérdida de ledgers, que es la causa raíz | Infraestructura |
| Patrón **Outbox** en los cuatro servicios | Entrega garantizada aunque el broker caiga tras el commit | Medio |
| *Reaper* que retome sagas no finales al arrancar | Recuperación aunque el mensaje se haya perdido del todo | Medio |
| `negative_acknowledge` ante fallas técnicas en el consumidor de saga | Cierra la ventana estrecha del `ack` en el `except` | Bajo |

### Hipótesis 3 — Consistencia transaccional

> Con sagas concurrentes fallando en puntos distintos después de la retención del
> pago, la discrepancia entre el dinero registrado y el Saga Log es exactamente
> `0`: no hay dinero fantasma ni dinero perdido.

| # | Criterio | Umbral | Corrida A | Corrida B |
|---|---|---|---|---|
| 3.1 | Discrepancia bruta (Σ \|desvío\| por saga) | = 0 | **0,00** ✔ | **0,00** ✔ |
| 3.2 | Sagas con dinero fantasma o perdido | 0 | **0** ✔ | **0** ✔ |
| 3.3 | Acreditaciones duplicadas | 0 | **0** ✔ | **0** ✔ |
| 3.4 | Sagas en estado `FALLIDA` | 0 | **0** ✔ | **0** ✔ |
| 3.5 | Movimiento del saldo = suma de acreditaciones | iguales | **✔** | **✔** |

## **Veredicto: SE CUMPLE. 5 de 5 criterios en ambas corridas.**

**Sustentación técnica.** Con 40 sagas concurrentes fallando en cuatro puntos
distintos —pago, asignación, ejecución en campo y acreditación—, la identidad
`cobrado = acreditado + custodia` se sostuvo saga por saga, con discrepancia bruta
de **0,00** en ambas corridas. El saldo de la billetera se movió exactamente por la
suma de las acreditaciones (3 100 101 en A, 930 046 en B): ni un peso entró o salió
por otra vía.

Tres mecanismos lo producen, y cada uno es verificable por separado:

- **Unidad de Trabajo por caso de uso.** En WalletBC el saldo y su movimiento se
  confirman en la misma transacción o no se confirma ninguno. No existe un estado
  intermedio donde el saldo subió sin dejar rastro auditable.
- **Idempotencia por referencia de saga.** La acreditación se identifica con
  `saga:{saga_id}:acreditacion` y la autorización con `saga:{saga_id}:autorizacion`.
  Cero acreditaciones duplicadas en 40 sagas concurrentes (criterio 3.3), cubierto
  además por la prueba `test_comando_reentregado_no_acredita_dos_veces`.
- **Compensación encadenada por confirmación.** El reverso del pago solo se da por
  bueno cuando llega `PagoTrabajoRevertidoV1`; si no llega, la saga cae a `FALLIDA`
  y el auditor la marca. **Las 16 compensaciones de ambas corridas se completaron
  íntegras: cero `FALLIDA`.**

**Sobre `EN_DISPUTA`.** Once sagas terminaron en disputa, con 3 410 105 COP en
custodia. El auditor no las cuenta como descuadre, y esa es la decisión de diseño
correcta: el servicio ya se prestó, así que revertir el cobro para "cuadrar" sería
regalar el trabajo del proveedor. Lo que el auditor sí exige es que **toda**
custodia esté respaldada por una saga `EN_DISPUTA` en el log; custodia sin respaldo
sería descuadre.

**Alcance de la conclusión.** La consistencia se sostiene mientras el broker esté
sano. La corrida C —auditoría posterior al corte duro del escenario 2— arrojó
2 800 173 COP de discrepancia bruta. Es decir: la lógica de compensación es
correcta, pero su corrección depende de que los mensajes lleguen. Consistencia y
disponibilidad no son propiedades independientes en esta arquitectura.

### Resumen ejecutivo de veredictos

| Escenario | Hipótesis | Veredicto | Evidencia principal |
|---|---|---|---|
| 1 — Elasticidad | Acepta y completa 4x la carga base sin degradarse | **SE CUMPLE** (rango nominal) | Aceptación p95 73,4 ms; saturación 0 % en 1600 sagas; techo ~30 sagas/s |
| 2 — Disponibilidad | Ninguna saga se pierde ante la caída del broker | **SE CUMPLE** en partición; **NO SE CUMPLE** con pérdida de ledgers | 100 % recuperado en 2,0 s (`pausa`) vs. 12 % (`caida`); Saga Log HTTP 200 siempre |
| 3 — Consistencia | Discrepancia de dinero estrictamente 0 | **SE CUMPLE** | Discrepancia bruta 0,00 en 40 sagas concurrentes; 0 duplicadas; 0 `FALLIDA` |

---

## 5. Guion del video de sustentación (≤ 45 min)

Presupuesto para los dos bloques pedidos; el resto del tiempo queda para la
arquitectura general, el patrón Saga y el BFF.

| Bloque | Duración |
|---|---|
| A — WalletBC en la saga | 12 min |
| B — Experimentos, métricas y validación de hipótesis | 15 min |

> Convención: **[pantalla]** indica qué mostrar; el resto es lo que se dice.

---

### Bloque A — El Bounded Context de Wallet en la Saga (12 min)

#### A.1 Por qué Wallet es el último paso y por qué eso importa (2 min)

**[pantalla: diagrama de los 5 pasos de la saga]**

«La Saga de Activación de Servicio tiene cinco pasos: creamos el trabajo
preliminar, PagosBC autoriza el pago, OperacionesBC asigna el proveedor,
OperacionesBC reporta que el trabajo se ejecutó en campo, y finalmente WalletBC
acredita la liquidación al proveedor.

Wallet es el último, y esa posición define todo su diseño. Los cuatro primeros
pasos son reversibles: si algo falla, compensamos en orden inverso. El quinto **no
se compensa**, y no es un descuido: para cuando llegamos a acreditarle al
proveedor, el trabajo físico ya se prestó. El cliente ya tiene el baño reparado.
Revertir el pago en ese punto sería quitarle al proveedor el dinero de un servicio
que sí entregó.

Entonces, cuando la acreditación falla de forma definitiva, el trabajo no se
cancela ni se revierte: pasa a `EN_DISPUTA`, y Operaciones lo resuelve a mano.
Perdemos automatismo a cambio de no perder dinero de nadie.

Esta decisión no es teórica: en nuestros experimentos once sagas terminaron
`EN_DISPUTA`, con tres millones cuatrocientos mil pesos en custodia. Nuestro
auditor de consistencia los cuenta como *custodia declarada*, no como descuadre — y
ya van a ver por qué eso es lo correcto.»

#### A.2 El contrato: cómo entra y cómo responde (2 min)

**[pantalla: `consumidor_comandos_wallet_pulsar.py`, líneas 12-14 y 97-143]**

«WalletBC no expone un endpoint para la saga: participa **solo por mensajería**.
Consume el comando `AcreditarProveedorV1` del tópico `comandos-wallet`, con
suscripción `Shared`, y responde en `eventos-wallet` con uno de dos eventos:
`WalletAcreditadaV1` si acreditó, o `AcreditacionFallidaV1` si agotó sus
reintentos.

Cada mensaje lleva el `saga_id` y el `command_type` en las **propiedades** de
Pulsar, no solo en el cuerpo, para poder filtrar sin deserializar. La clave de
partición es el `trabajo_id`, lo que mantiene el orden de los mensajes de una misma
saga aunque haya varias réplicas.

Fíjense en el detalle del *ack*, línea 89: WalletBC confirma el mensaje en **los
dos** desenlaces, incluso cuando la acreditación falló. La razón está en el
comentario de la clase: para cuando emite `AcreditacionFallidaV1` ya agotó su
política de reintentos, así que reentregar el comando no cambiaría el resultado. El
fallo continúa su curso en el orquestador, que es quien decide abrir la disputa.»

#### A.3 La regla de dominio: `acreditar_liquidacion` (2 min)

**[pantalla: `app/dominio/billetera/billetera.py`, método `acreditar_liquidacion`]**

«Acá está la parte que sí es dominio puro, sin FastAPI ni Pulsar de por medio.

WalletBC tiene dos formas de acreditar y **no** son la misma operación. El
`acreditar` administrativo es un ajuste contable. El `acreditar_liquidacion` es el
pago de un trabajo, y exige que la billetera esté **activa**: una billetera
suspendida no puede recibir la liquidación mientras Operaciones no resuelva por qué
está suspendida.

Y miren lo que hace cuando rechaza: antes de lanzar el error, emite el evento de
dominio `AcreditacionRechazada`. El rechazo no toca el saldo, pero sí queda
anunciado, porque que una liquidación fue rechazada es información de negocio, no
un detalle técnico que se pierde en un try/except.

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
`with self._fabrica_uow() as uow:`, y el saldo y su movimiento se confirman juntos
con `uow.confirmar()` o no se confirma ninguno. No existe un estado intermedio
donde el saldo subió sin que quedara el movimiento que lo explica. Los eventos de
dominio se despachan **después** del commit, nunca dentro.

Y esto no es una afirmación de diapositiva. **[pantalla: lista de tests]** Está
cubierto por `test_comando_reentregado_no_acredita_dos_veces`,
`test_confirmar_persiste_saldo_y_movimiento_juntos` y
`test_excepcion_a_mitad_del_caso_de_uso_revierte_la_transaccion`. Y en los
experimentos lo medimos: 40 sagas concurrentes, **cero acreditaciones
duplicadas**.»

#### A.5 Reintentos: distinguir lo transitorio de lo permanente (2 min)

**[pantalla: `ERRORES_PERMANENTES` y `PoliticaDeReintentos`]**

«WalletBC es quien decide cuántas veces vale la pena insistir, porque es el único
que sabe qué significa cada fallo.

La política son tres intentos con backoff exponencial: espera medio segundo, luego
uno, luego dos. Eso sirve para un fallo **transitorio** —una billetera bloqueada
que se reactiva, una caída puntual de la base—: darle tiempo al recurso a
recuperarse.

Pero hay fallos que no cambian por esperar: que el proveedor no tenga billetera,
que la moneda no corresponda, que el monto sea inválido. Esos están en
`ERRORES_PERMANENTES` y salen de inmediato, sin reintentar. Insistir ahí solo
retrasaría la disputa, que es lo que de verdad hay que abrir.

Tenemos una prueba bonita para esto:
`test_billetera_reactivada_entre_reintentos_termina_acreditando`. Simula que la
billetera se reactiva entre el intento uno y el dos, y verifica que la saga termina
bien. Esa es exactamente la situación para la que existe el backoff.»

#### A.6 Demostración en vivo (2 min)

**[pantalla: terminal]**

```bash
python3 -m scripts.probar_saga_orquestada --modo exito
```

«Miren el paso 5: `ACREDITAR_PROVEEDOR`, servicio `wallet-service`, estado
`EXITOSO`, y la saga queda `COMPLETADA_EXITOSA`.»

```bash
python3 -m scripts.probar_saga_orquestada --modo disputa-wallet
```

«Acá WalletBC agotó sus tres intentos y emitió `AcreditacionFallidaV1`. Fíjense en
qué **no** pasó: el pago no se revirtió y el trabajo no se canceló. La saga terminó
`EN_DISPUTA`, con el paso registrado como `ABRIR_DISPUTA_REVISION_MANUAL`.»

**[pantalla: `GET /wallet/billeteras?proveedor_id=prov-hda-expert-01` y sus movimientos]**

«Y del lado de la billetera se ve el movimiento con su `referencia_externa`:
`saga:...:acreditacion`. Esa referencia es la que después usa el auditor del
escenario 3 para cruzar el dinero contra el Saga Log — y es la que nos permitió
afirmar que la discrepancia es cero.»

---

### Bloque B — Experimentos, métricas y validación de hipótesis (15 min)

#### B.1 Cómo medimos y por qué así (2 min)

**[pantalla: tabla de los 3 escenarios]**

«Automatizamos tres experimentos, uno por escenario de calidad. Los tres miden el
sistema **desde afuera, por HTTP**, e imprimen un veredicto explícito contra
umbrales fijados de antemano.

Antes de los números, tres decisiones de medición.

La primera: **separamos dos latencias**. El `POST` que inicia la saga responde
`202` apenas crea el trabajo preliminar y publica el comando de pago; todo lo demás
pasa después, por Pulsar. Medimos por un lado la *aceptación* —lo que espera el
partner— y por otro la *saga completa*, con las marcas de tiempo del propio Saga
Log. Confundirlas es el error clásico al medir una arquitectura asíncrona:
reportaríamos 73 milisegundos cuando la transacción real puede tardar 57 segundos.

La segunda: reportamos la discrepancia de dinero **bruta**, no la neta. Lo
descubrimos probando el auditor contra un stub con errores inyectados a propósito:
un peso perdido y un peso fantasma del mismo tamaño se cancelan, y el total daba
cero con cuatro sagas rotas adentro. La cifra que vale es la suma de desvíos en
valor absoluto.

La tercera: cada saga lleva un monto distinto, para que un cruce entre
acreditaciones se delate por monto además de por referencia.

Una salvedad de honestidad: esto corrió en un portátil con Docker Desktop, no en la
EC2. Los valores absolutos cambiarán; la forma de las curvas y las conclusiones, no.»

#### B.2 Escenario 1 — Elasticidad (4 min)

**[pantalla: tabla de la corrida A]**

«La hipótesis: ante un pico de cuatro veces la carga base —una granizada que
dispara los siniestros— el sistema sigue aceptando en tiempo interactivo y termina
las sagas sin acumular pendientes.

Primera corrida, línea base 2 sagas por segundo hasta 8. Resultado: la aceptación
p95 pasó de 68 a 73 milisegundos. Un factor de **1,1** ante un aumento de carga de
4×. Cuatrocientas sagas, las cuatrocientas `COMPLETADA_EXITOSA`, saturación cero.

La hipótesis se cumple, pero no encontramos el límite. Así que subimos.

**[pantalla: tabla de la corrida B]**

Segunda corrida, línea base 10 hasta 40 sagas por segundo. Acá aparece la rodilla,
y está entre 10 y 20: la latencia de la saga completa salta de 0,21 segundos a
32 segundos p95, mientras la aceptación sigue en 353 milisegundos, todavía bajo el
umbral. A 30 por segundo la aceptación ya rompe el objetivo. A 40, el sistema solo
absorbe 30,46.

Pero miren la columna de la derecha: **la saturación siguió en cero en las ocho
etapas**. Mil doscientas sagas más, todas completadas. Ninguna se perdió, ninguna
quedó abierta. Y esa es la conclusión que quiero dejar: el límite que alcanzamos es
de **latencia**, no de **corrección**. El sistema encola bajo presión en vez de
descartar trabajo, que es justo lo que uno le pide a una arquitectura reactiva
frente a un pico de siniestros.

**[pantalla: tabla de 1 vs 2 réplicas]**

Y acá viene el resultado que no esperábamos. Levantamos una segunda réplica del
orquestador esperando mover el techo, y **el techo bajó**: de 30,46 a 27,66 sagas
por segundo.

Fuimos a los logs a entender por qué, y encontramos dos cosas. Primera: la réplica
dos procesó el 28 % de los eventos de saga —la suscripción `Shared` sí reparte—
pero inició **cero** sagas por HTTP, porque el gateway enruta `/trabajos` a un
único upstream. Segunda: aun con ese 28 % repartido, el throughput no subió, lo que
sitúa el cuello de botella en el broker standalone y en la contención sobre
`postgres-trabajos`, que ambas réplicas comparten y donde cada paso de cada saga
escribe en el Saga Log.

O sea: desacoplar por mensajería no basta para escalar si la puerta de entrada
síncrona no se balancea. Para que la táctica rinda hay que balancear el gateway y
separar el almacenamiento del Saga Log, no solo agregar contenedores.»

#### B.3 Escenario 2 — Disponibilidad (5 min)

**[pantalla: tabla comparativa `pausa` vs `caida`]**

«La hipótesis: si Pulsar se cae con sagas en tránsito, ninguna se pierde.

Lo derribamos de dos formas distintas a propósito, y la diferencia entre ellas *es*
el resultado. En modo `pausa` congelamos el contenedor: los datos del broker
sobreviven, que es lo que se parece a una partición de red. En modo `caida` lo
matamos y lo volvemos a levantar, y acá hay que ser honestos con nuestro propio
despliegue: nuestro Pulsar standalone arranca borrando su directorio de datos,
porque un bookie que cambia de dirección no puede recuperar sus ledgers.

Modo `pausa`: **nueve de nueve sagas retenidas se recuperaron solas, todas en dos
segundos** tras restablecer. La recuperación total fue de 16,4 segundos, de los
cuales 14,4 los consumió el arranque del propio broker. La arquitectura aportó dos
segundos.

Modo `caida`: **dos de diecisiete**. Las quince restantes quedaron detenidas en el
paso cinco, `ACREDITAR_PROVEEDOR` — el comando ya publicado se fue con los ledgers
borrados. Y le pudimos poner precio: corrimos el auditor del escenario tres sobre
esas sagas y dio **dos millones ochocientos mil pesos cobrados y no liquidados, en
catorce sagas**.

**Veredicto: la hipótesis se cumple ante partición temporal y no se cumple ante
pérdida de ledgers.**

Ahora, quiero destacar dos cosas.

La primera. **[pantalla: los dos resultados de la sonda]** En los dos modos, durante
toda la caída, el Saga Log respondió `HTTP 200`. Iniciar una saga nueva sí falló,
por timeout. Esa asimetría es el radio de impacto real: leer el Saga Log solo toca
PostgreSQL; iniciar una saga necesita publicar en Pulsar. La caída del broker
degrada nuestra capacidad de **avanzar** transacciones, no la de **auditarlas**. Ese
es exactamente el valor de haber persistido el Saga Log fuera del bus.

La segunda es una corrección que quiero hacer en público. Antes de correr el
experimento predijimos, leyendo el código, que el modo `pausa` recuperaría solo
parcialmente, porque nuestro consumidor de eventos de saga confirma el mensaje
aunque el manejo falle. **La medición nos refutó**: recuperó el 100 %. La
explicación es que con el broker congelado el consumidor no recibe nada, así que
ningún manejador corre y nada se confirma indebidamente. El riesgo del `ack` sigue
existiendo, pero su ventana exige un broker *parcialmente* disponible y es más
estrecha de lo que creíamos. Preferimos reportar esto a dejar la predicción
escrita como si fuera un hallazgo.

**[pantalla: tabla de correcciones]** Y sabemos qué hay que hacer, en orden de
impacto: un clúster de Pulsar con tres bookies y volumen persistente, que ataca la
causa raíz; Outbox en los cuatro servicios; un reaper que retome las sagas no
finales al arrancar —apoyándose en la idempotencia que ya demostramos que
funciona—; y el `negative_acknowledge` para cerrar la ventana estrecha del `ack`.»

#### B.4 Escenario 3 — Consistencia (4 min)

**[pantalla: tabla de corridas A y B]**

«La hipótesis: con sagas concurrentes fallando en puntos distintos después de la
retención del pago, la discrepancia de dinero es exactamente cero.

Cuarenta sagas en paralelo entre dos corridas, sorteando en cada una dónde falla:
en el pago, en la asignación, en la ejecución en campo o en Wallet. Después
auditamos cruzando **tres bases de datos distintas**: el Saga Log en
GestionDeTrabajos, el pago en PagosBC y el movimiento en WalletBC, cotejados por
las referencias `saga:{id}:autorizacion` y `saga:{id}:acreditacion`.

La identidad que verificamos es: **cobrado = acreditado + custodia**.

Resultado: **discrepancia bruta 0,00 en las dos corridas**. Cero acreditaciones
duplicadas. Cero sagas `FALLIDA`: las dieciséis compensaciones se completaron
íntegras. Y el saldo de la billetera se movió exactamente por la suma de las
acreditaciones, ni un peso por otra vía.

Acá está la parte conceptual que quiero destacar: **`EN_DISPUTA` no es un
descuadre, es custodia declarada.** Once sagas terminaron así, con tres millones
cuatrocientos mil pesos retenidos. El servicio ya se prestó, el cobro se sostiene, y
el Saga Log deja constancia de que Operaciones debe resolverlo. Un sistema que
"cuadrara" revirtiendo el cobro de un servicio ya prestado estaría regalando el
trabajo del proveedor a cambio de una métrica bonita. Lo que sí sería descuadre es
custodia **sin** una saga que la respalde, y eso es lo que el auditor verifica.

**Veredicto: se cumple, cinco de cinco criterios en ambas corridas**, sostenido en
tres mecanismos: la Unidad de Trabajo, que confirma saldo y movimiento juntos; la
idempotencia por referencia de saga; y la compensación encadenada por confirmación,
que solo da por buena una reversión cuando llega el evento que la confirma.

Con una acotación importante: **esto vale mientras el broker esté sano**. La misma
auditoría después del corte duro del escenario dos dio dos millones ochocientos mil
de discrepancia. La lógica de compensación es correcta, pero su corrección depende
de que los mensajes lleguen. Consistencia y disponibilidad no son propiedades
independientes en esta arquitectura.»

#### B.5 Cierre: qué aprendimos (2 min)

**[pantalla: tabla resumen de veredictos]**

«Cerrando los tres escenarios.

Elasticidad: **se cumple** en el rango nominal, con el techo identificado en unas
30 sagas por segundo. Y lo más valioso: mil seiscientas sagas, cero perdidas. El
sistema encola, no descarta.

Disponibilidad: **se cumple ante partición, no ante pérdida de ledgers**. Sabemos
exactamente por qué, cuánto cuesta —dos millones ochocientos mil pesos en catorce
sagas— y qué hacer. Y se cumple la parte de observabilidad: el Saga Log sobrevive a
la caída del bus.

Consistencia: **se cumple**, discrepancia bruta cero con cuarenta sagas
concurrentes fallando en cuatro puntos distintos.

Y una reflexión sobre el método. Tres de los hallazgos más valiosos no salieron de
confirmar lo que esperábamos, sino de lo contrario. La segunda réplica que empeoró
el rendimiento. La discrepancia neta que daba cero con cuatro sagas rotas, que
encontramos probando el auditor contra errores inyectados a propósito. Y nuestra
predicción sobre el modo `pausa`, que la medición refutó. Un experimento que solo
confirma lo que uno ya creía no estaba bien diseñado.»

---

## 6. Checklist antes de grabar

- [ ] Repetir cada configuración tres veces y reportar la mediana (§1.3).
- [ ] Si se sustenta sobre EC2, repetir las corridas allá: estas son de portátil.
- [ ] Guardar los CSV de las corridas como evidencia.
- [ ] Tener a mano una saga de cada desenlace para mostrar su `GET /sagas/{id}`.
- [ ] Verificar que el stack esté sano justo antes de grabar: `curl http://localhost/salud`.
- [ ] Limpiar las 16 sagas `EN_PROCESO` que dejó el escenario 2, o explicarlas si
      quedan visibles en `GET /sagas`.
- [ ] Confirmar que Pulsar y las bases estén arriba: hoy no tienen
      `restart: unless-stopped`, así que un reinicio deja las APIs corriendo sin
      broker ni bases — nos pasó al iniciar esta sesión de experimentos.
