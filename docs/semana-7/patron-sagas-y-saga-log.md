# Especificación del Patrón de Sagas y Saga Log
## Entrega Semana 7 — Hogar de los Alpes (HdA)

Este documento detalla el diseño, especificación técnica, implementación y auditoría de las transacciones distribuidas de larga duración (**Sagas**) y del almacén inmutable de eventos de coordinación (**Saga Log**) en el ecosistema de Hogar de los Alpes, en estricto cumplimiento de los Criterios 1, 2, 3 y 7 de la Semana 7.

---

## 1. Justificación del Patrón Transaccional

### 1.1 Modelo Seleccionado: Orquestación vs. Coreografía

Para coordinar la transacción de negocio de **Activación, Liquidación y Asignación de Trabajos**, se seleccionó el patrón de **Saga por Orquestación**, donde un coordinador centralizado en el Core Domain (`GestionDeTrabajosBC`) gobierna el ciclo de vida de la transacción, emite comandos asíncronos y procesa los eventos de respuesta.

Esta decisión se sustenta en cuatro pilares arquitectónicos:

1. **Visibilidad Global y Observabilidad:**
   En flujos de negocio que involucran dinero en tránsito y compromisos operativos con partners, dispersar el estado entre múltiples servicios mediante coreografía dificulta determinar en qué punto exacto falló una transacción. La orquestación centraliza la máquina de estados, permitiendo alimentar un **Saga Log** persistente con marcas de tiempo, payloads y causales de fallo de forma atómica.
2. **Centralización y Determinismo de la Compensación:**
   Ante un rechazo (ej. fondos insuficientes o indisponibilidad de proveedores), la orquestación ejecuta las transacciones de compensación en **orden estrictamente inverso**, evitando condiciones de carrera (*race conditions*) y garantizando idempotencia. En coreografía, coordinar compensaciones multidireccionales eleva exponencialmente el acoplamiento semántico y el riesgo de inconsistencias temporales.
3. **Prevención de Ciclos y Eventos Pasivo-Agresivos:**
   Se evita el antipatrón de eventos que ocultan comandos implícitos ("los platos están sucios"). Cada intención hacia servicios colaboradores se modela explícitamente como un **Comando** (`AutorizarPagoTrabajoV1`, `AsignarProveedorTrabajoV1`, `RevertirPagoTrabajoV1`), dejando los eventos para anunciar hechos consumados.
4. **Respeto a los Límites de Contexto Acotado (DDD):**
   `GestionDeTrabajosBC` actúa como orquestador al ser el dueño del agregado raíz `Trabajo`. No se introdujo un bus monolítico o ESB satélite anémico, sino un coordinador de aplicación especializado dentro del bounded context núcleo.

### 1.2 Microservicios Participantes en la Transacción

La saga involucra 4 microservicios autónomos, cada uno gobernando su propia base de datos relacional y sus reglas de invariantes mediante arquitectura hexagonal:

| Microservicio (Bounded Context) | Capa / Dominio | Rol en la Saga | Agregado Involucrado |
| :--- | :--- | :--- | :--- |
| **`gestion-trabajos-service`** | Core Domain | **Orquestador y Coordinador:** Inicia la saga, persiste el trabajo preliminar, gobierna el Saga Log, emite comandos y cancela, confirma o pone en disputa el trabajo. | `Trabajo` |
| **`pagos-service`** | Supporting / Fintech | **Custodia y Cobro Financiero:** Recibe comandos para autorizar/retener fondos y para ejecutar compensaciones de reverso. | `Pago` |
| **`operaciones-service`** | Supporting / Logística | **Asignación y Ejecución Operativa:** Recibe comandos para asignar proveedores/partners certificados y para liberar asignaciones ante fallos, y reporta cómo terminó el trabajo en campo. | `Partner` / `TrabajosDePartner` |
| **`wallet-service`** | Supporting / Fintech | **Liquidación al Proveedor:** Recibe el comando de acreditación, lo ejecuta en una transacción local con reintentos y responde con el resultado. | `Billetera` |

---

## 2. Especificación de la Máquina de Estados de la Saga

### 2.1 Estados Globales y Transiciones

El orquestador materializa el estado global de la transacción en la tabla `saga_instancias`:

```mermaid
stateDiagram-v2
    [*] --> INICIADA: POST /sagas/activar-servicio
    INICIADA --> EN_PROCESO: Paso 1 completado (Crear Trabajo)
    
    state EN_PROCESO {
        [*] --> ESPERANDO_PAGO: Emitir AutorizarPago
        ESPERANDO_PAGO --> PAGO_CONFIRMADO: Evento PagoAutorizado
        PAGO_CONFIRMADO --> ESPERANDO_ASIGNACION: Emitir AsignarProveedor
        ESPERANDO_ASIGNACION --> PROVEEDOR_ASIGNADO: Evento ProveedorAsignado
        PROVEEDOR_ASIGNADO --> ESPERANDO_EJECUCION: El proveedor ejecuta en campo
        ESPERANDO_EJECUCION --> TRABAJO_EJECUTADO: Evento EjecucionTrabajoCompletada
        TRABAJO_EJECUTADO --> ESPERANDO_ACREDITACION: Emitir AcreditarProveedor
        ESPERANDO_ACREDITACION --> PROVEEDOR_ACREDITADO: Evento WalletAcreditada
    }

    EN_PROCESO --> COMPLETADA_EXITOSA: Todos los pasos confirmados
    
    state COMPENSANDO {
        [*] --> LIBERANDO_PASO_3: Fallo en Ejecución
        LIBERANDO_PASO_3 --> REVERTIENDO_PASO_2: Evento AsignacionLiberada
        [*] --> REVERTIENDO_PASO_2: Fallo en Asignación
        REVERTIENDO_PASO_2 --> REVERTIENDO_PASO_1: Evento PagoRevertido
        REVERTIENDO_PASO_1 --> [*]: Cancelar Trabajo
    }

    EN_PROCESO --> COMPENSANDO: PagoRechazado, AsignacionRechazada o EjecucionFallida
    COMPENSANDO --> COMPENSADA: Compensaciones finalizadas
    COMPENSANDO --> FALLIDA: Error irrecuperable en compensación

    EN_PROCESO --> EN_DISPUTA: AcreditacionFallida (paso 5, no compensable)

    COMPLETADA_EXITOSA --> [*]
    COMPENSADA --> [*]
    EN_DISPUTA --> [*]
    FALLIDA --> [*]
```

El paso 5 es el único que no admite compensación: para cuando se acredita, el trabajo
físico ya se prestó. Por eso su fallo no lleva a `COMPENSANDO` sino a `EN_DISPUTA`.

### 2.2 Tópicos y Canales de Mensajería sobre Apache Pulsar

La comunicación asíncrona entre el orquestador y los servicios participantes se canaliza mediante tópicos persistentes dedicados en **Apache Pulsar**:

| Tópico Pulsar | Tipo de Mensaje | Emisor | Consumidor | Propósito |
| :--- | :---: | :---: | :---: | :--- |
| `persistent://public/default/comandos-pago` | **Comando** | Orquestador | `pagos-service` | `AutorizarPagoTrabajoV1`, `RevertirPagoTrabajoV1` |
| `persistent://public/default/eventos-pago` | **Evento** | `pagos-service` | Orquestador | `PagoTrabajoAutorizadoV1`, `PagoTrabajoRechazadoV1`, `PagoTrabajoRevertidoV1` |
| `persistent://public/default/comandos-operaciones` | **Comando** | Orquestador | `operaciones-service` | `AsignarProveedorTrabajoV1`, `LiberarAsignacionProveedorV1` |
| `persistent://public/default/eventos-operaciones` | **Evento** | `operaciones-service` | Orquestador | `ProveedorTrabajoAsignadoV1`, `AsignacionProveedorRechazadaV1`, `AsignacionProveedorLiberadaV1`, `EjecucionTrabajoCompletadaV1`, `EjecucionTrabajoFallidaV1` |
| `persistent://public/default/comandos-wallet` | **Comando** | Orquestador | `wallet-service` | `AcreditarProveedorV1` |
| `persistent://public/default/eventos-wallet` | **Evento** | `wallet-service` | Orquestador | `WalletAcreditadaV1`, `AcreditacionFallidaV1` |

Cada mensaje incluye en sus propiedades de cabecera: `command_type` / `event_type`, `saga_id` y `partition_key` (usando el `trabajo_id` para garantizar ordenamiento por partición).

---

## 3. Flujos Transaccionales

### 3.1 Flujo Exitoso (Happy Path)

Todos los pasos avanzan secuencialmente y alcanzan consistencia eventual:

```mermaid
sequenceDiagram
    autonumber
    actor Cliente as Cliente / BFF
    participant Orq as Orquestador (GestionTrabajos)
    participant Log as Saga Log (PostgreSQL)
    participant Pagos as PagosBC
    participant Ops as OperacionesBC
    participant Wallet as WalletBC

    Cliente->>Orq: POST /sagas/activar-servicio
    Orq->>Log: registrar_inicio_saga (INICIADA)
    Orq-->>Cliente: 202 Accepted (saga_id, trabajo_id)

    rect rgb(240, 248, 255)
        note over Orq, Log: Paso 1: Registro Local
        Orq->>Log: registrar_paso_iniciado(1, CREAR_TRABAJO_PRELIMINAR)
        Orq->>Orq: UoW: guardar(Trabajo PRELIMINAR) & confirmar()
        Orq->>Log: registrar_paso_completado(1)
    end

    rect rgb(240, 255, 240)
        note over Orq, Pagos: Paso 2: Retención Financiera
        Orq->>Log: registrar_paso_iniciado(2, AUTORIZAR_PAGO)
        Orq->>Pagos: Comando: AutorizarPagoTrabajoV1 (Pulsar)
        Pagos->>Pagos: UoW: procesar cobro/retención
        Pagos-->>Orq: Evento: PagoTrabajoAutorizadoV1 (Pulsar)
        Orq->>Log: registrar_paso_completado(2)
    end

    rect rgb(255, 250, 240)
        note over Orq, Ops: Paso 3: Asignación de Proveedor
        Orq->>Log: registrar_paso_iniciado(3, ASIGNAR_PROVEEDOR)
        Orq->>Ops: Comando: AsignarProveedorTrabajoV1 (Pulsar)
        Ops->>Ops: UoW: asignar profesional certificado
        Ops-->>Orq: Evento: ProveedorTrabajoAsignadoV1 (Pulsar)
        Orq->>Log: registrar_paso_completado(3)
    end

    rect rgb(255, 245, 250)
        note over Orq, Ops: Paso 4: Ejecución en campo (sin comando)
        Orq->>Log: registrar_paso_iniciado(4, EJECUTAR_TRABAJO)
        Ops-->>Orq: Evento: EjecucionTrabajoCompletadaV1 (Pulsar)
        Orq->>Log: registrar_paso_completado(4)
    end

    rect rgb(240, 255, 250)
        note over Orq, Wallet: Paso 5: Liquidación al Proveedor
        Orq->>Log: registrar_paso_iniciado(5, ACREDITAR_PROVEEDOR)
        Orq->>Wallet: Comando: AcreditarProveedorV1 (Pulsar)
        Wallet->>Wallet: UoW: acreditar saldo (idempotente por saga_id)
        Wallet-->>Orq: Evento: WalletAcreditadaV1 (Pulsar)
        Orq->>Log: registrar_paso_completado(5)
    end

    rect rgb(235, 255, 235)
        note over Orq, Log: Cierre Exitoso
        Orq->>Log: finalizar_saga(COMPLETADA_EXITOSA)
    end
```

### 3.2 Flujo Compensatorio ante Fallos (Compensación en Orden Inverso)

Cada fallo determina desde qué paso arranca el rollback semántico:

| Fallo | Evento que lo anuncia | Compensaciones, en orden inverso | Estado final |
| :--- | :--- | :--- | :--- |
| Pago rechazado (paso 2) | `PagoTrabajoRechazadoV1` | `CancelarTrabajo` (local). Aún no hay asignación que liberar. | `COMPENSADA` |
| Asignación rechazada (paso 3) | `AsignacionProveedorRechazadaV1` | `RevertirPagoTrabajoV1` → `CancelarTrabajo` | `COMPENSADA` |
| Ejecución fallida (paso 4) | `EjecucionTrabajoFallidaV1` | `LiberarAsignacionProveedorV1` → `RevertirPagoTrabajoV1` → `CancelarTrabajo` | `COMPENSADA` |
| Acreditación fallida (paso 5) | `AcreditacionFallidaV1` | **Ninguna.** El trabajo pasa a `EN_DISPUTA` | `EN_DISPUTA` |

Cada compensación espera la confirmación de la anterior antes de emitir la siguiente: el
reverso del pago solo se pide cuando OperacionesBC confirma `AsignacionProveedorLiberadaV1`,
y el trabajo solo se cancela cuando PagosBC confirma `PagoTrabajoRevertidoV1`. Encadenarlas
por confirmación —y no dispararlas en paralelo— es lo que evita las condiciones de carrera
que justificaron elegir orquestación sobre coreografía.

Demostración del rollback semántico cuando ocurre un fallo en el Paso 3 (`operaciones-service` sin disponibilidad de profesionales):

```mermaid
sequenceDiagram
    autonumber
    participant Orq as Orquestador (GestionTrabajos)
    participant Log as Saga Log (PostgreSQL)
    participant Pagos as PagosBC
    participant Ops as OperacionesBC

    note over Orq, Pagos: Pasos 1 y 2 completados con éxito
    Orq->>Log: registrar_paso_iniciado(3, ASIGNAR_PROVEEDOR)
    Orq->>Ops: Comando: AsignarProveedorTrabajoV1
    Ops-->>Orq: Evento: AsignacionProveedorRechazadaV1 (Sin cobertura)

    rect rgb(255, 230, 230)
        note over Orq, Log: Inicio de Compensación
        Orq->>Log: registrar_paso_fallido(3, error) & estado=COMPENSANDO

        note over Orq, Pagos: Compensación Paso 2 (Orden Inverso)
        Orq->>Log: registrar_paso_compensacion(2, COMPENSAR_REVERTIR_PAGO, EN_PROCESO)
        Orq->>Pagos: Comando: RevertirPagoTrabajoV1 (Pulsar)
        Pagos->>Pagos: UoW: liberar retención / reembolso
        Pagos-->>Orq: Evento: PagoTrabajoRevertidoV1 (Pulsar)
        Orq->>Log: registrar_paso_compensacion(2, COMPLETADO)

        note over Orq, Orq: Compensación Paso 1
        Orq->>Log: registrar_paso_compensacion(1, COMPENSAR_CREAR_TRABAJO, EN_PROCESO)
        Orq->>Orq: UoW: cancelar trabajo (motivo="Saga fallida por asignación")
        Orq->>Log: registrar_paso_compensacion(1, COMPENSADO)

        Orq->>Log: finalizar_saga(COMPENSADA, estado_consistente)
    end
```

El orquestador conserva la saga en `COMPENSANDO` después de enviar el comando de
reverso. Solo procesa la compensación local y establece `COMPENSADA` cuando
recibe `PagoTrabajoRevertidoV1` con `revertido=true`; si Pagos reporta un
reverso fallido, el paso queda en `ERROR` y la saga termina en `FALLIDA`.

### 3.3 Flujo `EN_DISPUTA`: la acreditación no se compensa

El paso 5 rompe la simetría del patrón, y a propósito. Cuando WalletBC va a acreditar, el
trabajo físico **ya se prestó**: el proveedor hizo la reparación y el cliente la recibió.
Compensar la saga significaría cancelar ese trabajo y devolverle el dinero al cliente por un
servicio que sí obtuvo, dejando además al proveedor sin cobrar lo que trabajó. La
compensación sería técnicamente correcta y comercialmente inaceptable.

```mermaid
sequenceDiagram
    autonumber
    participant Orq as Orquestador (GestionTrabajos)
    participant Log as Saga Log (PostgreSQL)
    participant Wallet as WalletBC
    participant Ops as Operaciones (humano)

    note over Orq, Wallet: Pasos 1 a 4 completados: el trabajo ya se ejecutó
    Orq->>Log: registrar_paso_iniciado(5, ACREDITAR_PROVEEDOR)
    Orq->>Wallet: Comando: AcreditarProveedorV1 (Pulsar)

    rect rgb(255, 245, 225)
        note over Wallet: Reintentos con backoff exponencial
        Wallet->>Wallet: Intento 1 → billetera bloqueada (espera 0,5 s)
        Wallet->>Wallet: Intento 2 → billetera bloqueada (espera 1 s)
        Wallet->>Wallet: Intento 3 → billetera bloqueada
    end

    Wallet-->>Orq: Evento: AcreditacionFallidaV1 (intentos=3)

    rect rgb(255, 235, 215)
        note over Orq, Log: Disputa, no compensación
        Orq->>Log: registrar_paso_fallido(5, motivo)
        Orq->>Orq: UoW: Trabajo.marcar_en_disputa(motivo)
        Orq->>Log: registrar_paso_compensacion(5, ABRIR_DISPUTA_REVISION_MANUAL, COMPENSADO)
        Orq->>Log: finalizar_saga(EN_DISPUTA, motivo)
    end

    Orq-->>Ops: Evento de integración: TrabajoEnDisputaV1
    note over Ops: Resuelve a mano: cierra o cancela el trabajo
```

Detalles de la política:

- **Los reintentos viven en WalletBC**, no en el orquestador: es quien sabe si el fallo es
  transitorio (billetera bloqueada, caída puntual de la base) o permanente (el proveedor no
  tiene billetera, la moneda no corresponde). Los permanentes no se reintentan.
- **La acreditación es idempotente** por `saga:{saga_id}:acreditacion`, así que una
  reentrega del comando no paga dos veces.
- **`EN_DISPUTA` no es un estado final del agregado.** El trabajo sigue admitiendo cerrarse o
  cancelarse: es el estado que espera la decisión de un humano, y el Saga Log conserva el
  motivo y el número de intentos para que esa decisión tenga contexto.
- **El Saga Log distingue tres finales**: `COMPLETADA_EXITOSA`, `COMPENSADA` y `EN_DISPUTA`.
  El tercero no es un error técnico, es trabajo pendiente para Operaciones.

---

## 4. Persistencia y Auditoría con Saga Log

### 4.1 Modelo de Datos Relacional

El Saga Log se almacena en PostgreSQL (`trabajos_db`) mediante dos entidades fuertemente tipadas:

#### Tabla `saga_instancias`
Registra la cabecera y el estado global de cada transacción:

| Campo | Tipo | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Identificador interno de registro. |
| `saga_id` | `UUID` | Unique, Index | Identificador global de trazabilidad de la transacción. |
| `tipo_saga` | `VARCHAR(60)` | Not Null | Nombre del workflow (`SagaActivacionServicio`). |
| `trabajo_id` | `UUID` | Index, Not Null | ID del agregado `Trabajo` asociado. |
| `estado_global` | `VARCHAR(40)` | Index, Not Null | `INICIADA`, `EN_PROCESO`, `COMPENSANDO`, `COMPENSADA`, `EN_DISPUTA`, `COMPLETADA_EXITOSA`, `FALLIDA`. |
| `paso_actual` | `VARCHAR(60)` | Not Null | Último paso registrado en el flujo. |
| `payload_inicial`| `JSON` | Nullable | Datos iniciales recibidos al arrancar la saga. |
| `error` | `TEXT` | Nullable | Detalle del error si la saga falló o fue compensada. |
| `fecha_creacion` | `TIMESTAMP TZ` | Index, Not Null | Marca de tiempo de inicio. |
| `fecha_actualizacion` | `TIMESTAMP TZ` | Not Null | Marca de tiempo de última transición. |

#### Tabla `saga_pasos`
Registra la línea de tiempo granular de cada interacción:

| Campo | Tipo | Restricción | Descripción |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | Primary Key | Identificador del paso. |
| `saga_instancia_id`| `UUID` | Foreign Key (`saga_instancias.id`), Index | Relación 1 a N con la instancia. |
| `paso_numero` | `INTEGER` | Not Null | Orden secuencial (1, 2, 3...). |
| `nombre_paso` | `VARCHAR(80)` | Not Null | Identificador semántico del paso o compensación. |
| `servicio_participante` | `VARCHAR(60)` | Not Null | Microservicio receptor o emisor. |
| `estado_paso` | `VARCHAR(30)` | Not Null | `INICIADO`, `EXITOSO`, `FALLIDO`, `COMPENSANDO`, `COMPENSADO`. |
| `comando_enviado` | `JSON` | Nullable | Payload del comando emitido por Pulsar. |
| `evento_recibido` | `JSON` | Nullable | Payload del evento de respuesta procesado. |
| `error` | `TEXT` | Nullable | Mensaje de rechazo o excepción técnica. |
| `fecha_inicio` | `TIMESTAMP TZ` | Not Null | Timestamp en que arrancó el paso. |
| `fecha_fin` | `TIMESTAMP TZ` | Nullable | Timestamp en que se confirmó el resultado. |

---

### 4.2 Consultas SQL de Monitoreo y Verificación

Las siguientes consultas SQL permiten auditar en vivo el progreso, salud y tiempos de respuesta de las sagas:

#### 1. Línea de tiempo cronológica de una Saga específica
```sql
SELECT 
    si.saga_id,
    si.estado_global,
    sp.paso_numero,
    sp.nombre_paso,
    sp.servicio_participante,
    sp.estado_paso,
    ROUND(EXTRACT(EPOCH FROM (sp.fecha_fin - sp.fecha_inicio))::numeric, 3) AS duracion_segundos,
    sp.error
FROM saga_instancias si
JOIN saga_pasos sp ON sp.saga_instancia_id = si.id
WHERE si.saga_id = 'e5b2a6ca-076e-44cc-837c-29676d81eb39'
ORDER BY sp.paso_numero ASC, sp.fecha_inicio ASC;
```

#### 2. Duración promedio de las sagas exitosas
```sql
SELECT 
    tipo_saga,
    COUNT(*) AS total_ejecutadas,
    ROUND(AVG(EXTRACT(EPOCH FROM (fecha_actualizacion - fecha_creacion)))::numeric, 3) AS duracion_promedio_segundos,
    MIN(EXTRACT(EPOCH FROM (fecha_actualizacion - fecha_creacion))) AS min_segundos,
    MAX(EXTRACT(EPOCH FROM (fecha_actualizacion - fecha_creacion))) AS max_segundos
FROM saga_instancias
WHERE estado_global = 'COMPLETADA_EXITOSA'
GROUP BY tipo_saga;
```

#### 3. Auditoría de transacciones compensadas, en disputa y causas de fallo
```sql
SELECT 
    saga_id,
    trabajo_id,
    estado_global,
    error AS motivo_compensacion,
    fecha_creacion,
    fecha_actualizacion
FROM saga_instancias
WHERE estado_global IN ('COMPENSADA', 'EN_DISPUTA', 'FALLIDA')
ORDER BY fecha_actualizacion DESC
LIMIT 20;
```

---

## 5. Guía de Reproducción de Pruebas

### 5.1 Prueba Unitaria Automatizada (Sin dependencias externas)
Ejecuta la máquina de estados completa en memoria validando el Happy Path de cinco pasos, las compensaciones en orden inverso (fallo en asignación y fallo en ejecución) y la política `EN_DISPUTA`:

```bash
python3 gestion-trabajos-service/scripts/test_unitario_saga.py
```

### 5.2 Prueba de Integración de Extremo a Extremo (con Docker Compose y Pulsar)
Con el stack arriba (`docker compose up -d`):

Desde `gestion-trabajos-service/`:

```bash
# 1. Camino exitoso completo (GestionTrabajos -> Pagos -> Operaciones -> Wallet):
python3 -m scripts.probar_saga_orquestada --modo exito

# 2. Fallo forzado en la asignación y compensación de pagos y trabajos:
python3 -m scripts.probar_saga_orquestada --modo compensar-operaciones

# 3. Fallo forzado en pagos y compensación del trabajo:
python3 -m scripts.probar_saga_orquestada --modo compensar-pago

# 4. Fallo en la ejecución en campo: libera la asignación, revierte el pago y cancela:
python3 -m scripts.probar_saga_orquestada --modo compensar-ejecucion

# 5. Acreditación fallida: agota reintentos y deja el trabajo EN_DISPUTA sin revertir nada:
python3 -m scripts.probar_saga_orquestada --modo disputa-wallet
```

Las pruebas de la transacción local de WalletBC (unidad de trabajo, idempotencia de la
acreditación y backoff) corren sin Pulsar, desde `wallet-service/`:

```bash
DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests
```

### 5.3 Consulta de la API REST del Saga Log
- **Iniciar Saga:** `POST http://localhost:8001/sagas/activar-servicio` (o por Gateway en `http://localhost/trabajos/sagas/activar-servicio`). Retorna `202 Accepted` con `saga_id`.
- **Consultar Trazabilidad:** `GET http://localhost:8001/sagas/{saga_id}`. Retorna el historial completo de pasos y estados.
