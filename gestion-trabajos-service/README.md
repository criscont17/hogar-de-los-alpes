# GestionDeTrabajosBC — Motor del ciclo de vida de los trabajos

Microservicio del **Core Domain** de Hogar de los Alpes. Orquesta el ciclo de vida de todo
trabajo, venga de Marketplace (B2C) o de un partner B2B2C:

- construye el flujo de sub-trabajos con sus dependencias;
- aplica las condiciones pactadas (tope, red de proveedores y SLA);
- gestiona novedades, como re-diagnósticos y cancelaciones;
- publica sus hechos por **Apache Pulsar** para OperacionesBC, Pagos, Crédito y los demás
  contextos.

**No conoce a ningún partner.** Las solicitudes de aseguradoras, bancos y comercios llegan a
[OperacionesBC](../operaciones-service/README.md), que traduce el formato de cada partner,
resuelve su acuerdo comercial y envía aquí el comando canónico `CrearTrabajoV1`. Por eso
integrar un partner nuevo no modifica ni redespliega este servicio: es la medida del escenario de
Modificabilidad #3.

En el mapa de contextos TO-BE
([`hda-context-map-to-be.cml`](../docs/semana-2/contextos-acotados/hda-context-map-to-be.cml))
es upstream `[OHS, PL]` de la mayoría de contextos. Su API REST y sus comandos son el *Open Host
Service*, y sus eventos versionados, el *Published Language*.

> El mapa TO-BE menciona Apache Kafka; esta implementación usa Apache Pulsar. El puerto
> `MessageBroker` aísla esa decisión.

## Arquitectura

```
gestion-trabajos-service/
├── Dockerfile
├── requirements.txt
├── .env.example
├── collections/                  # Colección Postman del motor de trabajos
├── scripts/                      # Publicar comandos y escuchar eventos en Pulsar
└── app/
    ├── seedwork/
    │   ├── dominio/              # Entity, ValueObject, AggregateRoot, DomainEvent, DomainError
    │   └── aplicacion/           # DomainEventHandler, IntegrationEvent, ApplicationError
    ├── dominio/
    │   ├── trabajo/              # Agregado Trabajo, SubTrabajo, objetos valor, flujo, eventos
    │   └── errores/
    ├── aplicacion/
    │   ├── comandos/  queries/  dtos/
    │   ├── puertos/              # UnidadDeTrabajo, DomainEventDispatcher, MessageBroker
    │   ├── manejadores/          # auditar, publicar en Pulsar, traductores
    │   └── eventos_integracion/  # contrato público versionado (V1, V2)
    └── infraestructura/
        ├── configuracion.py
        ├── contenedor.py         # raíz de composición compartida por REST y Pulsar
        └── adaptadores/
            ├── entrada/
            │   ├── api/          # FastAPI: rutas de trabajos
            │   └── mensajeria/   # consumidor de comandos de Pulsar
            └── salida/           # persistencia/  eventos/  mensajeria/ (Pulsar, logs, memoria)
```

DDD, arquitectura hexagonal y CQS, igual que WalletBC y OperacionesBC.

- `app/dominio/`: Python puro. No conoce partners, formatos, FastAPI, SQLAlchemy ni Pulsar.
- `app/aplicacion/`: un handler por comando o query, DTOs `dataclass` y puertos. No importa
  infraestructura.
- `app/infraestructura/contenedor.py`: decide qué adaptador hay detrás de cada puerto. La API
  REST y el consumidor de comandos de Pulsar ejecutan los mismos casos de uso.

## Modelo de dominio

Lenguaje ubicuo tomado del event storming TO-BE
([imagen](../docs/semana-2/lenguaje-ubicuo/eventstorming-TO-BE-flujo-trabajo-con-novedades.png)):

| Concepto del negocio | En el código |
|---|---|
| Trabajo | Agregado raíz `Trabajo` |
| Sub-trabajo | Entidad `SubTrabajo`: categoría, proveedor, cotización y evidencias |
| Flujo del trabajo (grafo de dependencias) | `flujo.ordenar_flujo`: valida el grafo (sin ciclos) y define qué arranca en paralelo |
| Condiciones pactadas | Objeto valor `CondicionesDelTrabajo`: tope, red de proveedores y SLA, congelados al crear el trabajo |
| Naturaleza del trabajo cambiada (re-diagnóstico) | `Trabajo.registrar_rediagnostico` |
| Trabajo cerrado (evento pivote) | `Trabajo.cerrar` → `TrabajoCerrado` con la liquidación de cada proveedor |

Ciclo de vida de un sub-trabajo:

```
Bloqueado ──terminan todas sus dependencias──▶ Pendiente ──asignar──▶ Asignado ──iniciar──▶ EnEjecucion ──completar──▶ Completado
    ▲                                                                      │
    └─────────── un re-diagnóstico lo congela (conserva el proveedor) ─────┘
```

Reglas que protege el agregado:

- **Inicio:** un sub-trabajo solo inicia si tiene proveedor y sus dependencias terminaron ("no
  se instalan muebles si la tubería no está lista").
- **Completar:** exige al menos una evidencia. Al completar, los dependientes cuyas dependencias
  terminaron todas se desbloquean solos.
- **Asignar:** valida que el proveedor esté en la red permitida y que el costo acumulado no
  supere el tope. Si falla, emite `AsignacionRechazada` aunque no guarde nada.
- **Re-diagnóstico:** agrega el sub-trabajo del hallazgo y congela los que dependen de él. Si
  alguno ya inició, se rechaza completo.
- **Cerrar y cancelar:** cerrar exige todo completado. Cancelar liquida lo que alcanzó a
  completarse, para que Pagos pueda compensar.

## Escenarios de calidad

Los dos escenarios se demuestran con OperacionesBC y este servicio funcionando juntos. Las
decisiones sobre la capa anti-corrupción, los acuerdos y el circuit breaker por partner están
en el [README de OperacionesBC](../operaciones-service/README.md#decisiones-arquitectónicas-importantes).

Lo que aporta GestionDeTrabajosBC a cada uno:

| Escenario | Aporte de este servicio |
|---|---|
| Modificabilidad #3 | El agregado `Trabajo` solo conoce `CondicionesDelTrabajo` (tope, red, SLA), sin nada propio de un partner. Integrar un partner nuevo no toca ni reinicia este servicio. |
| Interoperabilidad #9 | Contrato canónico `CrearTrabajoV1`, idempotente por referencia de partner; eventos de integración versionados; y `CreacionDeTrabajoRechazadaV1` para que el partner se entere de los rechazos aunque haya solicitado por mensajería. Nunca llama a un partner, así que su caída no lo afecta. |
| Escalabilidad #4 | La suscripción `Shared` sobre `comandos-trabajo` reparte los comandos `CrearTrabajoV1` entre todas las instancias corriendo; agregar una réplica no requiere ningún cambio de código. Experimento y resultados en [`scripts/carga_escalabilidad.py`](scripts/carga_escalabilidad.py). |

### Experimento de Escalabilidad #4

`scripts/carga_escalabilidad.py` simula la "llegada masiva de siniestros desde partners":
publica `N` comandos `CrearTrabajoV1` en `comandos-trabajo` y mide, para cada uno, el tiempo
entre publicarlo y recibir su `TrabajoCreadoV2` en `eventos-trabajo` — esa es la latencia de
"aceptación" en una arquitectura asíncrona, donde no hay una respuesta HTTP que cronometrar.

```bash
# con Pulsar y este servicio corriendo (docker compose up -d pulsar gestion-trabajos)
python -m scripts.carga_escalabilidad --num 200
```

Para comparar 1 instancia contra varias (la táctica de escalado horizontal del escenario):

```bash
docker compose --profile escalabilidad up -d --build gestion-trabajos-2
python -m scripts.carga_escalabilidad --num 200   # repetir con la réplica activa
```

Ambas instancias comparten la suscripción `gestion-trabajos` (`Shared`) sobre el mismo tópico,
así que Pulsar reparte la carga entre las dos automáticamente. El script reporta latencia
p50/p95/p99 y el porcentaje de comandos confirmados, y los compara contra la medida de la
respuesta definida en la Entrega 3 (p95 < 500ms, p99 < 1s, ≥99.95% persistido).

## Eventos y comandos con Apache Pulsar

| Tópico | Dirección | Contenido |
|---|---|---|
| `persistent://public/default/eventos-trabajo` | Publica | Eventos de integración en JSON |
| `persistent://public/default/comandos-trabajo` | Consume (suscripción `gestion-trabajos`, `Shared`) | Comandos de OperacionesBC y otros contextos |

Cada evento viaja con las propiedades `event_type`, `event_version`, `event_name`,
`event_id`, `deprecado` y, si aplica, `partner_id`, para que el consumidor filtre sin leer el
cuerpo. La clave de partición es `trabajo_id` (o la referencia del partner cuando la creación se
rechaza): con suscripciones `Key_Shared`, los hechos de un mismo trabajo llegan en orden.

| Evento | Cuándo | Consumidor natural |
|---|---|---|
| `TrabajoCreadoV2` (y `TrabajoCreadoV1`, deprecado) | Al crear el trabajo | OperacionesBC, Marketplace |
| `CreacionDeTrabajoRechazadaV1` | La solicitud no formó un trabajo válido | OperacionesBC (avisa al partner), Marketplace |
| `ProveedorAsignadoV1` / `AsignacionRechazadaV1` | Asignación, reasignación o rechazo por las condiciones | OperacionesBC |
| `SubTrabajoIniciadoV1`, `SubTrabajoCompletadoV1`, `SubTrabajoDesbloqueadoV1` | Avance del flujo | OperacionesBC, Marketplace |
| `TrabajoRediagnosticadoV1` | Cambio de alcance | OperacionesBC |
| `TrabajoCanceladoV1` | Cancelación, con liquidaciones de lo completado | PagosBC (compensación), OperacionesBC |
| `TrabajoCerradoV1` | Cierre | PagosBC (libera el pago), CreditoBC, OperacionesBC |

Comandos aceptados (propiedad `command_type`, cuerpo JSON):

- `CrearTrabajoV1`: los campos de `POST /trabajos`. Cuando lo envía OperacionesBC agrega
  `canal: "Partner"`, `partner_id`, `referencia_externa` y `condiciones`
  (`monto_maximo`, `proveedores_permitidos`, `sla_horas`).
- `AsignarProveedorV1`, `IniciarSubTrabajoV1`, `CompletarSubTrabajoV1`,
  `RegistrarRediagnosticoV1`, `CancelarTrabajoV1`, `CerrarTrabajoV1`.

El consumidor confirma (*ack*) los éxitos y los rechazos de negocio, porque reintentar no
cambia el resultado. Pide reentrega (*nack*) ante conflictos de concurrencia o fallas técnicas;
tras tres reentregas, Pulsar mueve el mensaje a la *dead letter queue*.

## Requisitos y ejecución

El servicio usa el puerto **8001** y crea sus tablas al arrancar. La documentación
interactiva queda en <http://localhost/trabajos/docs> cuando corre en Docker (detrás de la
entrada pública; ver el [README raíz](../README.md#despliegue-con-docker-y-entrada-pública)) y en
<http://localhost:8001/docs> cuando corre local (opciones B y C).

### Opción A — Todo en Docker (recomendada)

Desde la raíz del repositorio:

```bash
docker compose up -d --build --wait gestion-trabajos operaciones
```

Levanta este servicio, OperacionesBC, sus bases de datos y Apache Pulsar.

- **Logs:** `docker compose logs -f gestion-trabajos`.
- **Después de cambiar código:** reconstruya con `docker compose up -d --build gestion-trabajos`.
- **Detener:** `docker compose stop` detiene todo sin borrar datos.
- **Pulsar:** arranca siempre con datos limpios y consume bastante CPU; deténgalo cuando no lo
  use.

### Opción B — Local con PostgreSQL y Pulsar en Docker

```bash
cd gestion-trabajos-service
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # ponga MESSAGE_BROKER=pulsar y PULSAR_CONSUMIR_COMANDOS=true
docker compose -f ../docker-compose.yml up -d postgres-trabajos pulsar
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8001
```

Para ver Pulsar en acción:

```bash
python -m scripts.escuchar_eventos --suscripcion pagos-bc --evento TrabajoCerrado
python -m scripts.publicar_comando CrearTrabajoV1 scripts/ejemplos/crear_trabajo.json
```

### Opción C — Sin Docker (SQLite y eventos en el log)

```powershell
New-Item -ItemType Directory -Force app\data
$env:DATABASE_URL="sqlite+pysqlite:///./app/data/trabajos.db"
$env:MESSAGE_BROKER="logging"
.venv\Scripts\python.exe -m uvicorn app.infraestructura.adaptadores.entrada.api.main:app --port 8001
```

Cada evento aparece en la consola con el sobre que viajaría por Pulsar. Sin Pulsar no hay
comunicación con OperacionesBC: solo funciona el flujo de Marketplace.

### Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://trabajos:trabajos@localhost:5433/trabajos_db` | Conexión a la base |
| `MESSAGE_BROKER` | `logging` | `logging`, `pulsar` o `memoria` (guarda los eventos sin publicarlos) |
| `PULSAR_URL` | `pulsar://localhost:6650` | Broker de Pulsar |
| `PULSAR_TOPICO_EVENTOS` / `PULSAR_TOPICO_COMANDOS` | `eventos-trabajo` / `comandos-trabajo` | Tópicos |
| `PULSAR_SUSCRIPCION_COMANDOS` | `gestion-trabajos` | Suscripción del consumidor de comandos |
| `PULSAR_CONSUMIR_COMANDOS` | `false` | Arranca el consumidor de comandos |

## API REST

| Método y ruta | Descripción |
|---|---|
| `POST /trabajos` | Crea un trabajo de Marketplace con su flujo de sub-trabajos |
| `GET /trabajos?estado=&partner_id=&limite=` | Lista trabajos |
| `GET /trabajos/{trabajo_id}` | Consulta un trabajo |
| `POST /trabajos/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/asignar` | Asigna o reasigna proveedor con su cotización |
| `POST /trabajos/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/iniciar` | Inicia un sub-trabajo |
| `POST /trabajos/{trabajo_id}/sub-trabajos/{sub_trabajo_id}/completar` | Completa con evidencias |
| `POST /trabajos/{trabajo_id}/rediagnosticar` | Registra un hallazgo que cambia el alcance |
| `POST /trabajos/{trabajo_id}/cancelar` | Cancela el trabajo |
| `POST /trabajos/{trabajo_id}/cerrar` | Cierra el trabajo |

Ejemplo:

```bash
curl -X POST http://localhost:8001/trabajos \
  -H 'Content-Type: application/json' \
  -d '{"descripcion":"Humedad en la cocina","urgencia":"Alta",
       "ubicacion":{"pais":"CO","ciudad":"Bogota","direccion":"Calle 80 # 20-10"},
       "sub_trabajos":[
         {"clave":"plomeria","categoria":"Plomeria","descripcion":"Reparar fuga"},
         {"clave":"pintura","categoria":"Pintura","descripcion":"Pintar muro","depende_de":["plomeria"]}]}'
```

Valores permitidos:

- `urgencia`: `Baja`, `Media`, `Alta` o `Emergencia`.
- `categoria`: `Plomeria`, `Electricidad`, `Carpinteria`, `Pintura` o `Baldoseria`.
- filtro `estado`: `Creado`, `EnEjecucion`, `Cerrado` o `Cancelado`.

Códigos de respuesta:

- `201`: trabajo creado.
- `200`: operación exitosa.
- `400`: datos inválidos.
- `404`: el trabajo o el sub-trabajo no existe.
- `409`: transición no permitida, proveedor fuera de la red, sobrecosto o conflicto de concurrencia.

## Decisiones arquitectónicas importantes

Cada decisión registra el problema que resuelve, la alternativa descartada y lo que cuesta.
Las decisiones de la capa anti-corrupción con partners están en OperacionesBC (DO-01 a DO-05).

### DA-01. Arquitectura hexagonal con DDD táctico y CQS

- **Contexto:** es el core domain y el upstream del que dependen casi todos los contextos. Sus
  reglas deben evolucionar sin arrastrar decisiones de tecnología.
- **Decisión:** el agregado `Trabajo` es la única puerta para cambiar sub-trabajos; cada caso de
  uso es un comando o una query con su handler; dominio y aplicación solo conocen puertos.
- **Alternativa descartada:** un modelo anémico con la lógica en servicios o rutas.
- **Consecuencias:** más archivos y mapeos, a cambio de sustituir persistencia y mensajería sin
  tocar las reglas.

### DA-02. El core no conoce partners (escenario #3)

- **Contexto:** más de 30 partners con reglas propias. Si el motor de trabajos las conociera,
  cada partner nuevo lo modificaría y obligaría a redesplegarlo.
- **Decisión:** los formatos y acuerdos de los partners viven en OperacionesBC. Este servicio
  solo recibe el comando canónico `CrearTrabajoV1` con las condiciones ya resueltas, y expone
  eventos.
- **Alternativa descartada:** la capa anti-corrupción dentro de este servicio. Fue la primera
  versión de la POC y obligaba a reconstruir el core en cada onboarding.
- **Consecuencias:** creación asíncrona para los partners, y un contexto más que operar.

### DA-03. Condiciones del trabajo congeladas al crear (escenario #3)

- **Contexto:** los partners renegocian sus acuerdos, pero un trabajo en curso debe respetar lo
  pactado al solicitarlo.
- **Decisión:** `CondicionesDelTrabajo` guarda tope, red y SLA junto con el trabajo y no cambia
  después.
- **Alternativa descartada:** consultar el acuerdo vigente en cada operación; acopla el core a
  OperacionesBC en línea y altera trabajos ya pactados.
- **Consecuencias:** una regla que no quepa en esos tres valores obliga a ampliar el contrato
  canónico. Es el riesgo aceptado del escenario 3.

### DA-04. Creación idempotente y rechazo como evento (escenario #9)

- **Contexto:** los comandos llegan por mensajería (pueden reentregarse), y quien los envía no
  recibe la excepción si la creación falla.
- **Decisión:** la pareja `(partner_id, referencia_externa)` es única: repetir el comando
  devuelve el trabajo existente. Si la solicitud no forma un trabajo válido, se publica
  `CreacionDeTrabajoRechazadaV1` con el motivo.
- **Alternativa descartada:** validar el flujo también en OperacionesBC; duplicaría las reglas
  del dominio en otro contexto.
- **Consecuencias:** el partner se entera de un rechazo de forma asíncrona, consultando su
  trabajo o recibiendo la novedad.

### DA-05. Eventos de integración versionados y separados de los de dominio (escenario #9)

- **Contexto:** consumidores con ciclos de release ajenos a HdA; un cambio interno no puede
  romperlos.
- **Decisión:** clases propias en `eventos_integracion/`, con tipos primitivos y versión en el
  nombre. `TrabajoCreadoV1` (deprecado) y `TrabajoCreadoV2` conviven con el mismo `event_id`.
- **Alternativa descartada:** publicar el evento de dominio serializado.
- **Consecuencias:** hay que mantener un traductor por versión. Política: como máximo dos
  versiones activas por evento.

### DA-06. Apache Pulsar detrás del puerto `MessageBroker`

- **Contexto:** la arquitectura objetivo es orientada a eventos y el mapa TO-BE nombra Kafka.
- **Decisión:** Apache Pulsar, con un tópico de eventos y uno de comandos, `trabajo_id` como
  clave de partición y *dead letter queue* para comandos que fallan por causas técnicas.
- **Alternativas descartadas:**
  - Kafka: el puerto deja reversible la elección de plataforma.
  - Un tópico por evento: con propiedades en el mensaje, cada consumidor filtra sin leer el cuerpo.
- **Consecuencias:** Pulsar standalone consume bastante CPU en local; existe el adaptador
  `logging` para trabajar sin él.

### DA-07. Unidad de trabajo: la transacción la decide el caso de uso

- **Contexto:** antes cada repositorio hacía `commit` dentro de `guardar`, así que la
  transacción la decidía el adaptador de persistencia. Un caso de uso que escribiera dos
  veces podía dejar la mitad guardada, y la aplicación no tenía forma de revertir.
- **Decisión:** el puerto `UnidadDeTrabajo` delimita la transacción. El handler abre el
  bloque, obtiene el repositorio de la unidad (`uow.trabajos`) y confirma al final; el
  repositorio solo hace `flush`. Al salir del bloque se revierte lo no confirmado.
- **Alternativa descartada:** seguir confirmando en el repositorio. Es menos código, pero
  mezcla la política (cuándo es definitivo un cambio) con el detalle técnico de guardar.
- **Consecuencias:** los errores de integridad y de versión se traducen en la unidad de
  trabajo, y los eventos se despachan **después** de confirmar, no antes.
- **Detalle aprendido:** no se usan *savepoints* para reintentar dentro de la transacción,
  porque el driver de SQLite los ejecuta fuera de transacción y persistía cambios sin
  confirmar. Cuando una escritura falla, el caso de uso revierte la unidad y vuelve a leer.

### DA-08. Publicar después del commit, sin Outbox (por ahora)

- **Decisión:** el caso de uso guarda y luego despacha los eventos. Un suscriptor que falla se
  registra y no afecta la respuesta.
- **Alternativa descartada:** Outbox, que da entrega garantizada pero agrega infraestructura.
- **Consecuencias:** si Pulsar cae justo después del commit, un evento puede perderse. Es el
  primer pendiente para producción.

### DA-09. Base de datos propia y bloqueo optimista

- **Decisión:** base `trabajos_db` exclusiva y versión en la fila del trabajo. Si otra
  operación lo guardó entre la lectura y la escritura, se responde 409 (o se reentrega el comando).
- **Alternativa descartada:** bloqueo pesimista, que retiene filas durante toda la operación.
- **Consecuencias:** ante operaciones concurrentes sobre el mismo trabajo, el cliente puede
  recibir un conflicto y debe reintentar.

### DA-10. Raíz de composición compartida por REST y Pulsar

- **Decisión:** el cableado vive en `app/infraestructura/contenedor.py` y lo usan la API y el
  consumidor de comandos. Ahí se crea la unidad de trabajo de cada petición o mensaje.
- **Consecuencias:** un comando produce los mismos eventos llegue por REST o por Pulsar.

## Flujo de prueba con Postman

- **Motor de trabajos:** la colección de [`collections/`](collections/README.md) tiene el flujo
  completo de Marketplace (dependencias, desbloqueo, re-diagnóstico y cierre) y los casos de
  error del agregado.
- **Escenarios de calidad #9 y #3:** usan OperacionesBC y este servicio a la vez. Su colección y
  el paso a paso están en
  [`operaciones-service/collections/`](../operaciones-service/collections/README.md).

## Pendientes conocidos

- **Outbox** para garantizar la entrega de eventos.
- **Migraciones versionadas** en lugar de `create_all`: un cambio en `modelos_orm.py` no altera
  tablas existentes.
- **Validar proveedores contra ProveedoresBC**: hoy `proveedor_id` es un identificador opaco.
