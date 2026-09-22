# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Idioma

Todo el repositorio está en español: nombres de clases, módulos, carpetas, comentarios,
docstrings, READMEs y mensajes de commit. Mantenga esa convención — código nuevo en español,
con Conventional Commits en español (`feat(pagos): ...`, `fix: ...`).

## Comandos

Todo se levanta con Docker Compose desde la raíz:

```bash
docker compose up -d --build --wait          # stack completo (5 servicios + 4 Postgres + Pulsar + gateway)
docker compose up -d --build gestion-trabajos   # reconstruir un solo servicio tras cambiar código
docker compose logs -f pagos                 # logs de un servicio
docker compose stop                          # detener sin borrar datos
PUERTO_GATEWAY=8088 docker compose up -d --wait     # si el puerto 80 está ocupado
```

Réplica extra para el experimento de escalabilidad (perfil aparte, no arranca por defecto):

```bash
docker compose --profile escalabilidad up -d --build gestion-trabajos-2
```

### Ejecutar un servicio suelto

Cada servicio tiene su propio `requirements.txt` y venv. El módulo ASGI es
`app.infraestructura.adaptadores.entrada.api.main:app` en los cuatro microservicios de dominio,
y `app.main:app` en el BFF:

```bash
cd gestion-trabajos-service && python -m venv .venv && pip install -r requirements.txt
docker compose -f ../docker-compose.yml up -d postgres-trabajos pulsar
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8001
```

Sin Docker: `DATABASE_URL=sqlite+pysqlite:///./app/data/<servicio>.db` y `MESSAGE_BROKER=logging`
(archivo, nunca `:memory:` — SQLite abre una base por conexión). Sin Pulsar no hay comunicación
entre bounded contexts.

### Pruebas

No hay pytest ni runner unificado; son scripts y `unittest`:

```bash
# Unidad de Trabajo de PagosBC (suite completa)
cd pagos-service && DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests
# un solo test
cd pagos-service && DATABASE_URL="sqlite:///:memory:" python3 -m unittest tests.test_unidad_de_trabajo -v

# Unidad de Trabajo y paso de acreditación de la saga en WalletBC
cd wallet-service && DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests

# Saga: prueba unitaria en memoria (happy path, compensaciones y disputa)
cd gestion-trabajos-service && python3 scripts/test_unitario_saga.py
# Saga: integración contra Docker + Pulsar
# modos: exito | compensar-pago | compensar-operaciones | compensar-ejecucion | disputa-wallet
cd gestion-trabajos-service && python3 -m scripts.probar_saga_orquestada --modo exito

# Escalabilidad #4: publica N comandos y mide latencia p50/p95/p99 hasta el evento de respuesta
cd gestion-trabajos-service && python -m scripts.carga_escalabilidad --num 200

# Inspeccionar Pulsar a mano
cd gestion-trabajos-service && python -m scripts.escuchar_eventos --suscripcion pagos-bc --evento TrabajoCerrado
cd gestion-trabajos-service && python -m scripts.publicar_comando CrearTrabajoV1 scripts/ejemplos/crear_trabajo.json
```

La verificación funcional real del proyecto son las **colecciones Postman** en
`*/collections/` (flujos completos, casos de error y escenarios de calidad), no pruebas
automatizadas.

Nota: `wallet-service/env/` es un virtualenv que quedó en el árbol de trabajo. Exclúyalo de
búsquedas y ediciones.

## Arquitectura

Migración del monolito de Hogar de los Alpes (servicios para el hogar) a microservicios
reactivos. Cinco servicios Python/FastAPI detrás de un gateway Nginx, comunicados por
**Apache Pulsar**, cada uno con su propio PostgreSQL.

| Servicio | Rol | Puerto | Prefijo gateway |
|---|---|---|---|
| `gestion-trabajos-service` | **Core Domain**: agregado `Trabajo`, ciclo de vida, **orquestador de la saga** | 8001 | `/trabajos` |
| `operaciones-service` | Partners B2B2C: acuerdos comerciales + ACL por formato (REST/SOAP/webhooks) | 8002 | `/operaciones` |
| `pagos-service` | Checkout y pagos a proveedores; ACL + circuit breaker por PSP | 8003 | `/pagos` |
| `wallet-service` | Billeteras de proveedores; último paso de la saga (acreditación) | 8000 | `/wallet` |
| `bff-service` | Fachada HTTP síncrona; sin base ni dominio propio | 8005 | `/api` |

Solo el gateway escucha en `0.0.0.0:80`; APIs, bases y Pulsar quedan en `127.0.0.1`
(`IP_PUERTOS_INTERNOS=0.0.0.0` para exponerlas a propósito). Use `127.0.0.1`, no `localhost`:
sin listener IPv6 se pierden ~2 s por petición. Cada API arranca con `UVICORN_ROOT_PATH` igual
a su prefijo, por lo que Swagger solo carga a través del gateway (`/trabajos/docs`).

### Estructura interna (idéntica en los cuatro servicios de dominio)

DDD táctico + hexagonal + CQS. El BFF es la excepción: `app/{main,config,clients,schemas}.py`
y `app/routers/`.

```
app/
├── seedwork/          Entity, ValueObject, AggregateRoot, DomainEvent, DomainError,
│                      DomainEventHandler, IntegrationEvent (+ CircuitBreaker en pagos/operaciones)
├── dominio/           Python puro. Ignora FastAPI, SQLAlchemy y Pulsar.
├── aplicacion/        comandos/ queries/ dtos/ puertos/ manejadores/ eventos_integracion/
│                      (+ sagas/ en gestion-trabajos). No importa infraestructura.
└── infraestructura/
    ├── configuracion.py   variables de entorno
    ├── contenedor.py      raíz de composición: qué adaptador hay detrás de cada puerto
    └── adaptadores/
        ├── entrada/api/        rutas FastAPI + schemas Pydantic + mappers
        ├── entrada/mensajeria/ consumidores de Pulsar
        ├── acl_partners/ | acl_psp/   capa anti-corrupción (un adaptador por formato/PSP)
        └── salida/             persistencia/ eventos/ mensajeria/
```

Reglas que sostienen esa separación:

- **`contenedor.py` es la única raíz de composición**, compartida por la API REST y los
  consumidores de Pulsar: un mismo comando produce los mismos eventos llegue por HTTP o por
  mensaje. Adaptadores sin estado se cachean con `@lru_cache`; la unidad de trabajo se crea
  **una por petición o por mensaje**.
- **Unidad de Trabajo**: la transacción la delimita el caso de uso, no el repositorio. El
  patrón fijo del handler es `with self._uow as uow:` → operar sobre `uow.<repositorio>` →
  `uow.confirmar()`. Los repositorios solo hacen `flush()`. Los eventos de dominio se despachan
  **fuera del bloque**, después de confirmar. Los cuatro servicios de dominio lo aplican.
- **Eventos de integración ≠ eventos de dominio**: clases aparte en
  `aplicacion/eventos_integracion/` con tipos primitivos y sufijo de versión (`TrabajoCreadoV2`).
  La conversión vive solo en `aplicacion/manejadores/traductores.py`. Máximo dos versiones
  activas por evento; la vieja se marca `deprecado`.
- **Un suscriptor que falla no arrastra a los demás**: el dispatcher aísla y registra. No hay
  Outbox — si el broker cae tras el commit, el evento se pierde (pendiente conocido).
- **Bloqueo optimista** (versión en la fila) → `409` o *nack* del comando ante conflicto.
- **`create_all` al arrancar**, sin migraciones versionadas: un cambio en `modelos_orm.py` no
  altera tablas existentes.

### Mensajería y límites entre contextos

Los servicios **nunca se llaman síncronamente entre sí** (salvo el BFF, que solo consume
contratos REST publicados). Todo lo demás va por Pulsar:

| Tópico | Productor → Consumidor |
|---|---|
| `comandos-trabajo` | OperacionesBC → GestionDeTrabajos (susc. `gestion-trabajos`, **Shared** — reparte entre réplicas, base del escenario de escalabilidad) |
| `eventos-trabajo` | GestionDeTrabajos → OperacionesBC, PagosBC (susc. `pagos-bc`, `Key_Shared`) |
| `eventos-pago` | PagosBC → (WalletBC, futuro) |
| `comandos-pago` / `eventos-pago` | Orquestador ↔ PagosBC (saga) |
| `comandos-operaciones` / `eventos-operaciones` | Orquestador ↔ OperacionesBC (saga) |
| `comandos-wallet` / `eventos-wallet` | Orquestador ↔ WalletBC (saga) |

Cada mensaje lleva en propiedades `event_type`/`command_type`, `event_version`, `event_id`,
`deprecado` y, cuando aplica, `saga_id` y `partner_id`, para filtrar sin deserializar el cuerpo.
La clave de partición es `trabajo_id`. El consumidor hace *ack* de éxitos **y de rechazos de
negocio** (reintentar no cambia el resultado) y *nack* solo ante fallas técnicas o conflictos de
concurrencia; a las tres reentregas el mensaje va a la DLQ.

El puerto `MessageBroker` abstrae Pulsar: `MESSAGE_BROKER` acepta `pulsar`, `logging` (imprime
el sobre que viajaría) o `memoria`. Los consumidores se activan con banderas por servicio
(`PULSAR_CONSUMIR_COMANDOS`, `PULSAR_CONSUMIR_EVENTOS_TRABAJO`, `PULSAR_CONSUMIR_EVENTOS_SAGA`, …)
— ver `docker-compose.yml`.

### Saga por orquestación

El orquestador vive en el Core Domain (`gestion-trabajos-service/app/aplicacion/sagas/`) porque
es dueño del agregado `Trabajo`. Cinco pasos: (1) crear trabajo preliminar (local) →
(2) `AutorizarPagoTrabajoV1` a PagosBC → (3) `AsignarProveedorTrabajoV1` a OperacionesBC →
(4) `EJECUTAR_TRABAJO`, sin comando: Operaciones reporta `EjecucionTrabajoCompletadaV1` →
(5) `AcreditarProveedorV1` a WalletBC.

Ante fallo en los pasos 2–4 compensa en orden inverso, **encadenando por confirmación**
(`LiberarAsignacionProveedorV1` → `RevertirPagoTrabajoV1` → cancelar trabajo): cada
compensación se pide solo cuando llega el evento que confirma la anterior. El paso 5 **no se
compensa**: si WalletBC agota sus reintentos y emite `AcreditacionFallidaV1`, el trabajo pasa a
`EN_DISPUTA` (revisión manual de Operaciones) porque el servicio ya se prestó.

Cada transición se persiste en el **Saga Log** (`saga_instancias`, `saga_pasos`) y se consulta
con `GET /sagas/{id}`. Estados finales: `COMPLETADA_EXITOSA`, `COMPENSADA`, `EN_DISPUTA`,
`FALLIDA`. `POST /sagas/activar-servicio` acepta
`simular_fallo_en_paso: "PAGO" | "OPERACIONES" | "EJECUCION" | "WALLET"` para forzar cada
desenlace en demos. Diseño completo en `docs/semana-7/patron-sagas-y-saga-log.md`.

### Invariantes de dominio que conviene conocer antes de tocar código

- **El core no conoce partners.** Formatos y acuerdos viven en OperacionesBC; a
  GestionDeTrabajos solo llega el comando canónico `CrearTrabajoV1` con las condiciones ya
  resueltas. Integrar un partner nuevo no debe modificar ni redesplegar el core (escenario de
  Modificabilidad #3). Lo mismo con los PSPs: agregar uno es tocar `acl_psp/registro.py`, no el
  agregado `Pago`.
- **`CondicionesDelTrabajo`** (tope, red de proveedores, SLA) se congela al crear el trabajo;
  renegociar un acuerdo no altera trabajos en curso.
- **Creación idempotente**: `(partner_id, referencia_externa)` es única; repetir el comando
  devuelve el trabajo existente. Un rechazo se publica como `CreacionDeTrabajoRechazadaV1`, no
  como excepción.
- **`Trabajo` es la única puerta** para modificar sub-trabajos (desbloqueo por dependencias,
  evidencias al completar, validación de red y tope al asignar, re-diagnóstico).
- **Lo ya ejecutado no se compensa.** Si la liquidación al proveedor falla, el trabajo pasa a
  `EN_DISPUTA` (no se cancela ni se revierte el pago): el cliente ya recibió el servicio. Los
  reintentos de esa acreditación viven en WalletBC, que es quien distingue un fallo transitorio
  (billetera bloqueada) de uno permanente (el proveedor no tiene billetera).
- **`Billetera.acreditar_liquidacion` exige la billetera activa**, a diferencia del
  `acreditar` administrativo, y es idempotente por `saga:{saga_id}:acreditacion`.

## Documentación

- `README.md` raíz: despliegue, rutas del gateway, guía EC2 y mapa de entregables por semana.
- README por servicio: modelo de dominio, contratos y **decisiones arquitectónicas numeradas**
  (`DA-01…DA-11` en gestion-trabajos, `DO-01…DO-05` en operaciones) con alternativa descartada y
  consecuencias. Al tomar una decisión de arquitectura nueva, agregue una entrada con ese formato.
- `docs/semana-2/`: modelado estratégico DDD en DSL de ContextMapper (`.cml`).
- `docs/semana-7/`: sagas, BFF, experimentación y TO-BE refinado.

## Ramas

`main` (estable) ← `develop` (integración) ← ramas de feature (`feature/...`, `chore/...`).
