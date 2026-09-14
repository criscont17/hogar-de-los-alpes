# GestionDeTrabajosBC — Motor del ciclo de vida de los trabajos

Microservicio del **Core Domain** de Hogar de los Alpes. Orquesta el ciclo de vida de todo
trabajo, venga de Marketplace (B2C) o de un partner B2B2C (aseguradora, banco o comercio):
construye el flujo de sub-trabajos con sus dependencias, aplica el acuerdo comercial del
partner, gestiona novedades (re-diagnósticos, cancelaciones) y publica sus hechos por
**Apache Pulsar** para Pagos, Operaciones, Crédito y los propios partners.

En el mapa de contextos TO-BE
([`hda-context-map-to-be.cml`](../docs/semana-2/contextos-acotados/hda-context-map-to-be.cml))
es upstream `[OHS, PL]` de Marketplace, Siniestros, Pagos, Crédito y Operaciones: su API REST
es el *Open Host Service* y sus eventos versionados, el *Published Language*.

> El mapa TO-BE menciona Apache Kafka; esta implementación usa Apache Pulsar. El puerto
> `MessageBroker` aísla esa decisión: cambiar de plataforma es escribir otro adaptador.

## Arquitectura

```
gestion-trabajos-service/
├── README.md
├── Dockerfile
├── requirements.txt
├── .env.example
├── collections/                  # Colección Postman
├── ejemplos/onboarding/          # Partner listo para demostrar el onboarding
├── scripts/                      # Publicar comandos y escuchar eventos en Pulsar
└── app/
    ├── seedwork/
    │   ├── dominio/              # Entity, ValueObject, AggregateRoot, DomainEvent, DomainError
    │   ├── aplicacion/           # DomainEventHandler, IntegrationEvent, ApplicationError
    │   └── infraestructura/      # CircuitBreaker
    ├── dominio/
    │   ├── trabajo/              # Agregado Trabajo, SubTrabajo, objetos valor, flujo, eventos
    │   └── errores/
    ├── aplicacion/
    │   ├── comandos/  queries/  dtos/
    │   ├── puertos/              # DomainEventDispatcher, MessageBroker, AdaptadorDePartner, CatalogoDePartners
    │   ├── manejadores/          # auditar, publicar en Pulsar, sincronizar con partner, traductores
    │   └── eventos_integracion/  # contrato público versionado (V1, V2)
    └── infraestructura/
        ├── configuracion.py
        ├── contenedor.py         # raíz de composición compartida por REST y Pulsar
        └── adaptadores/
            ├── entrada/
            │   ├── api/          # FastAPI: rutas de trabajos y de partners
            │   └── mensajeria/   # consumidor de comandos de Pulsar
            ├── salida/           # persistencia/  eventos/  mensajeria/ (Pulsar, logs, memoria)
            └── acl_partners/     # capa anti-corrupción: un adaptador por partner
```

DDD, arquitectura hexagonal y CQS.

- `app/dominio/`: Python puro. No conoce partners, formatos, FastAPI, SQLAlchemy ni Pulsar.
- `app/aplicacion/`: un handler por comando o query, DTOs `dataclass` y puertos. No importa
  infraestructura.
- `app/infraestructura/contenedor.py`: decide qué adaptador hay detrás de cada puerto. En
  WalletBC ese cableado vive en `dependencias.py`; aquí se sacó de la API porque dos
  adaptadores de entrada (REST y el consumidor de Pulsar) ejecutan los mismos casos de uso.
- `app/infraestructura/adaptadores/acl_partners/`: traduce en ambos sentidos (solicitudes
  entrantes y novedades salientes), por eso no está ni en `entrada/` ni en `salida/`.

Regla de dependencias: ningún archivo de `app/dominio` ni de `app/aplicacion` importa
`app.infraestructura`, FastAPI, SQLAlchemy ni Pulsar, y ninguno menciona a un partner
concreto.

## Modelo de dominio

Lenguaje ubicuo tomado del event storming TO-BE
([imagen](../docs/semana-2/lenguaje-ubicuo/eventstorming-TO-BE-flujo-trabajo-con-novedades.png)):

| Concepto del negocio | En el código |
|---|---|
| Trabajo | Agregado raíz `Trabajo` |
| Sub-trabajo | Entidad `SubTrabajo`: categoría, proveedor, cotización y evidencias |
| Flujo del trabajo (grafo de dependencias) | `flujo.ordenar_flujo`: valida el grafo (sin ciclos) y define qué arranca en paralelo |
| Acuerdo comercial / reglas del partner | Objeto valor `AcuerdoComercial`: tope, red de proveedores y SLA, congelados al crear el trabajo |
| Naturaleza del trabajo cambiada (re-diagnóstico) | `Trabajo.registrar_rediagnostico` |
| Trabajo cerrado (evento pivote) | `Trabajo.cerrar` → `TrabajoCerrado` con la liquidación de cada proveedor |

Ciclo de vida de un sub-trabajo:

```
Bloqueado ──terminan todas sus dependencias──▶ Pendiente ──asignar──▶ Asignado ──iniciar──▶ EnEjecucion ──completar──▶ Completado
    ▲                                                                      │
    └─────────── un re-diagnóstico lo congela (conserva el proveedor) ─────┘
```

Reglas que protege el agregado:

- Un sub-trabajo solo inicia si tiene proveedor y sus dependencias terminaron ("no se
  instalan muebles si la tubería no está lista").
- Completar exige al menos una evidencia. Al completar, los dependientes cuyas dependencias
  terminaron todas se desbloquean solos (`SubTrabajoDesbloqueado`).
- Asignar valida que el proveedor esté en la red del acuerdo y que el costo acumulado no
  supere el tope. Si falla, emite `AsignacionRechazada` aunque no guarde nada, con el mismo
  patrón que `DebitoRechazado` en WalletBC.
- El re-diagnóstico agrega el sub-trabajo del hallazgo y congela los que dependen de él. Si
  alguno ya inició, se rechaza completo y el agregado queda intacto.
- Cerrar exige todo completado. Cancelar liquida lo que alcanzó a completarse, para que
  Pagos pueda compensar.

## Escenarios de calidad

```mermaid
flowchart LR
    subgraph PARTNERS["Partners B2B2C"]
        SA["Seguros de los Alpes<br/>REST JSON"]
        BA["Banco Andino<br/>SOAP XML"]
        MH["Muebles del Hogar<br/>webhooks"]
    end
    subgraph ACL["Capa anti-corrupción (acl_partners/)"]
        ASA["SegurosAlpesAdapter"]
        ABA["BancoAndinoAdapter"]
        AMH["MueblesHogarAdapter"]
        SYNC["Sincronizador por partner<br/>hilo + cola + circuit breaker"]
    end
    subgraph NUCLEO["Núcleo: dominio y aplicación"]
        UC["CrearTrabajoDesdePartnerHandler<br/>puerto AdaptadorDePartner"]
        AG["Agregado Trabajo"]
        BUS["Bus de eventos de dominio"]
    end
    PUL[("Apache Pulsar<br/>eventos-trabajo")]

    SA -->|formato propio| ASA
    BA -->|formato propio| ABA
    MH -->|formato propio| AMH
    ASA & ABA & AMH -->|SolicitudDeTrabajo canónica| UC
    UC --> AG --> BUS
    BUS -->|eventos de integración V1/V2| PUL
    BUS -->|eventos de integración V1/V2| SYNC
    SYNC -.->|formato del partner| SA & BA & MH
```

### Interoperabilidad (escenario 9)

| Decisión | Implementación | Cómo verificarlo |
|---|---|---|
| ACL con las reglas de partner | Cada partner tiene un adaptador que implementa `AdaptadorDePartner`. Traduce su formato y resuelve sus reglas (tope por plan, red homologada, SLA por prioridad) a `CondicionesDelAcuerdo`. Lo que no puede traducir completo se rechaza con 400. | Carpetas 02 y 04 de Postman |
| Eventos de integración versionados | Clases separadas en `eventos_integracion/` con tipos primitivos. `TrabajoCreadoV1` (deprecado) y `TrabajoCreadoV2` se publican a la vez; cada mensaje de Pulsar lleva `event_version` y `deprecado`. Política: como máximo dos versiones activas por evento. | Log `trabajos.integration_events` o `python -m scripts.escuchar_eventos` |
| Circuit breaker por adaptador | `SincronizadorDePartner`: breaker, hilo y cola propios por partner. Un fallo deja la novedad como *sincronización degradada* y se reintenta; al vencer `PARTNER_CB_RECUPERACION_SEGUNDOS` el circuito prueba de nuevo y entrega lo pendiente en orden. | Carpeta 03 de Postman |

Cómo se verifica cada medida de la respuesta:

- **"Un partner nuevo se integra sin modificar el dominio central"**: la carpeta 05 de
  Postman integra una cooperativa argentina con formato de texto plano copiando solo su
  adaptador (`ejemplos/onboarding/`). El mismo request pasa de 404 a 201.
- **"100 % de las transacciones se traducen correctamente al modelo canónico"**: la
  traducción es todo o nada. Un código, plan o servicio sin equivalencia rechaza la
  solicitud entera; nunca se crea un trabajo con una traducción parcial. Reintentar la
  misma referencia no duplica el trabajo.
- **"Ante falla del partner, se recupera automáticamente en segundos sin degradar a los
  otros"**: con un partner caído la API responde de inmediato (la entrega corre en el hilo
  de ese partner), su circuito se abre sin tocar el de los demás, y al volver el partner se
  entrega lo pendiente sin intervención (carpeta 03 de Postman).

### Modificabilidad (escenario 3)

| Decisión | Implementación | Cómo verificarlo |
|---|---|---|
| Arquitectura hexagonal + ACL como adaptador de entrada | El agregado `Trabajo` solo conoce `AcuerdoComercial` (tope, red, SLA). Planes de póliza, niveles SOAP y fases de instalación viven en el archivo de cada partner. | Carpeta 05 de Postman |
| Clean Architecture: "crear trabajo desde partner" depende de un puerto genérico | `CrearTrabajoDesdePartnerHandler` recibe `CatalogoDePartners` y delega en la misma creación que usa Marketplace. | `git diff --stat -- app/dominio app/aplicacion` vacío después de la carpeta 05 |

**"0 % de componentes del dominio de GestionDeTrabajosBC modificados"**: integrar un partner
es un archivo nuevo en `acl_partners/` más una línea en `registro.py`. Después de hacerlo,
`git diff --stat -- app/dominio app/aplicacion` debe quedar vacío.

Las decisiones que sostienen ambos escenarios, con sus alternativas y trade-offs, están en
[Decisiones arquitectónicas importantes](#decisiones-arquitectónicas-importantes). El paso a
paso para demostrarlos está en
[Flujo de prueba de los escenarios con Postman](#flujo-de-prueba-de-los-escenarios-con-postman).

## Eventos y comandos con Apache Pulsar

| Tópico | Dirección | Contenido |
|---|---|---|
| `persistent://public/default/eventos-trabajo` | Publica | Eventos de integración en JSON |
| `persistent://public/default/comandos-trabajo` | Consume (suscripción `gestion-trabajos`, `Shared`) | Comandos de otros bounded contexts |

Cada evento viaja con las propiedades `event_type`, `event_version`, `event_name`,
`event_id`, `deprecado` y, si aplica, `partner_id`, para que el consumidor filtre sin leer
el cuerpo. La clave de partición es `trabajo_id`: con suscripciones `Key_Shared`, los
hechos de un mismo trabajo llegan en orden aunque haya varios consumidores.

| Evento | Cuándo | Consumidor natural |
|---|---|---|
| `TrabajoCreadoV2` (y `TrabajoCreadoV1`, deprecado) | Al crear el trabajo | Marketplace, Operaciones (SLA) |
| `ProveedorAsignadoV1` | Asignación o reasignación | Operaciones, partner |
| `AsignacionRechazadaV1` | Proveedor fuera de la red o sobrecosto | Operaciones, partner |
| `SubTrabajoIniciadoV1`, `SubTrabajoCompletadoV1`, `SubTrabajoDesbloqueadoV1` | Avance del flujo | Marketplace, Operaciones |
| `TrabajoRediagnosticadoV1` | Cambio de alcance | Siniestros / partner, Operaciones |
| `TrabajoCanceladoV1` | Cancelación, con liquidaciones de lo completado | PagosBC (compensación) |
| `TrabajoCerradoV1` | Cierre | PagosBC (libera el pago), CreditoBC |

Comandos aceptados (propiedad `command_type`, cuerpo JSON con los mismos campos de la API):
`CrearTrabajoV1`, `CrearTrabajoDesdePartnerV1`, `AsignarProveedorV1`, `IniciarSubTrabajoV1`,
`CompletarSubTrabajoV1`, `RegistrarRediagnosticoV1`, `CancelarTrabajoV1` y `CerrarTrabajoV1`.

El consumidor confirma (*ack*) los éxitos y los rechazos de negocio, porque reintentar no
cambia el resultado. Pide reentrega (*nack*) ante conflictos de concurrencia o fallas
técnicas; tras tres reentregas, Pulsar mueve el mensaje a la *dead letter queue*.

Igual que en WalletBC, los eventos se publican después del commit y un subscriptor que
falla no afecta a los demás. Garantizar la entrega si Pulsar está caído requiere el patrón
Outbox, que queda pendiente.

## Partners integrados

| `partner_id` | Formato | Reglas que traduce | Novedades que recibe |
|---|---|---|---|
| `seguros-alpes` | REST con JSON propio | Tope por plan (BASICO 1,5 M · PLUS 4 M · PREMIUM 10 M COP), red homologada, SLA por prioridad | Proveedor asignado, cambio de alcance, anulación, cierre |
| `banco-andino` | SOAP (XML), México | Tope por orden en MXN, etapas convertidas en dependencias, SLA por nivel | Conclusión, cancelación, cotización rechazada |
| `muebles-hogar` | Webhooks JSON | Fases de instalación por ítem, tope por país, SLA standard/express | Paso completado, reprogramación, cancelación, cierre |

Cada adaptador documenta su formato con un ejemplo en su propio archivo. Los cores de los
partners se simulan con `ClientePartnerSimulado`, que registra lo recibido en el log y
permite simular caídas.

### Integrar un partner nuevo

1. Crear `app/infraestructura/adaptadores/acl_partners/<partner>.py` con una clase que
   herede de `AdaptadorDePartnerBase`, declare `PARTNER_ID` e implemente
   `traducir_solicitud`, `traducir_estado` y `traducir_evento`.
2. Agregar la clase a `ADAPTADORES_REGISTRADOS` en `registro.py`.
3. Reiniciar el servicio (en Docker, reconstruir la imagen) y probarlo con la carpeta 05
   de Postman.

El circuit breaker, la cola de reintentos y el endpoint `/partners/<partner_id>/trabajos`
quedan disponibles sin más cambios.

Para demostrarlo hay un partner listo sin registrar:
[`ejemplos/onboarding/cooperativa_sur.py`](ejemplos/onboarding/cooperativa_sur.py). Es una
cooperativa argentina que envía órdenes en texto plano. La carpeta 05 de la colección
Postman ejecuta el mismo request antes de copiarlo (404) y después (201).

## Requisitos y ejecución

Se necesita Python 3.11 o posterior. Todos los comandos se ejecutan desde el directorio del
microservicio:

```bash
cd hogar-de-los-alpes/gestion-trabajos-service
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

El servicio usa el puerto **8001** para convivir con WalletBC (8000). La documentación
interactiva queda en <http://localhost:8001/docs>. Las tablas se crean al arrancar.

### Opción A — PostgreSQL y Apache Pulsar con Docker

```bash
docker compose -f ../docker-compose.yml up -d postgres-trabajos pulsar
```

Pulsar en modo standalone tarda cerca de 30 segundos en quedar sano (`docker compose ps`).
En `.env`, active Pulsar:

```
MESSAGE_BROKER=pulsar
PULSAR_CONSUMIR_COMANDOS=true
```

```bash
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8001
```

Para ver Pulsar en acción, en otras dos terminales:

```bash
# Simula a PagosBC escuchando los cierres
python -m scripts.escuchar_eventos --suscripcion pagos-bc --evento TrabajoCerrado

# Simula a Marketplace enviando un comando
python -m scripts.publicar_comando CrearTrabajoV1 scripts/ejemplos/crear_trabajo.json
```

### Opción B — Sin Docker (SQLite y eventos en el log)

```bash
mkdir -p app/data
export DATABASE_URL=sqlite+pysqlite:///./app/data/trabajos.db
export MESSAGE_BROKER=logging
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload --port 8001
```

Con `MESSAGE_BROKER=logging`, cada evento aparece en la consola con el sobre que viajaría
por Pulsar (`trabajos.integration_events`).

### Opción C — Servicio desplegado en Docker

Desde la raíz del repositorio, un solo comando construye la imagen y levanta el servicio con
su base y Pulsar. Espera a que todo quede sano:

```bash
docker compose up -d --build --wait gestion-trabajos
```

- La API queda en <http://localhost:8001>, así que la colección Postman funciona igual. No
  ejecute al mismo tiempo un `uvicorn` local en el puerto 8001.
- Dentro de Docker el servicio usa `postgres-trabajos:5432` y `pulsar:6650`. Desde el host
  siguen publicados en 5433 y 6650, así que los scripts de `scripts/` funcionan igual.
- Logs: `docker compose logs -f gestion-trabajos`.
- La imagen contiene el código. Después de cambiarlo (por ejemplo, al integrar el partner
  de la carpeta 05 de Postman), reconstruya con
  `docker compose up -d --build gestion-trabajos`.
- Detener sin borrar datos: `docker compose stop`. Pulsar standalone consume bastante CPU
  y memoria; deténgalo cuando no lo use.

### Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://trabajos:trabajos@localhost:5433/trabajos_db` | Conexión a la base |
| `MESSAGE_BROKER` | `logging` | `logging`, `pulsar` o `memoria` (guarda los eventos sin publicarlos) |
| `PULSAR_URL` | `pulsar://localhost:6650` | Broker de Pulsar |
| `PULSAR_TOPICO_EVENTOS` / `PULSAR_TOPICO_COMANDOS` | `eventos-trabajo` / `comandos-trabajo` | Tópicos |
| `PULSAR_CONSUMIR_COMANDOS` | `false` | Arranca el consumidor de comandos |
| `PARTNER_CB_UMBRAL_FALLOS` | `3` | Fallos consecutivos que abren el circuito de un partner |
| `PARTNER_CB_RECUPERACION_SEGUNDOS` | `10` | Tiempo con el circuito abierto antes de probar de nuevo |
| `PARTNER_SINCRONIZACION_ASINCRONA` | `true` | Entrega a los partners en hilos propios |

## Cómo probar los escenarios

Con el servicio en el puerto 8001 (cualquiera de las opciones anteriores), importe en
Postman la colección de [`collections/`](collections/README.md) y siga el
[flujo de prueba de los escenarios con Postman](#flujo-de-prueba-de-los-escenarios-con-postman)
al final de este documento.

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
| `POST /partners/{partner_id}/trabajos` | Crea un trabajo desde la solicitud del partner, en su formato |
| `GET /partners/{partner_id}/trabajos/{referencia}` | El partner consulta con su propia referencia |
| `GET /partners` · `GET /partners/{partner_id}/salud` | Estado del circuito y de la sincronización |
| `PUT /partners/{partner_id}/simulacion` | Simula la caída o recuperación del core del partner |

Ejemplo, crear un trabajo con dependencias:

```bash
curl -X POST http://localhost:8001/trabajos \
  -H 'Content-Type: application/json' \
  -d '{"descripcion":"Humedad en la cocina","urgencia":"Alta",
       "ubicacion":{"pais":"CO","ciudad":"Bogota","direccion":"Calle 80 # 20-10"},
       "sub_trabajos":[
         {"clave":"plomeria","categoria":"Plomeria","descripcion":"Reparar fuga"},
         {"clave":"pintura","categoria":"Pintura","descripcion":"Pintar muro","depende_de":["plomeria"]}]}'
```

Ejemplo, una aseguradora crea un siniestro en su formato:

```bash
curl -X POST http://localhost:8001/partners/seguros-alpes/trabajos \
  -H 'Content-Type: application/json' \
  -d '{"numeroSiniestro":"SA-2026-000123","poliza":{"numero":"H-88231","plan":"PLUS"},
       "prioridad":"ALTA","descripcionSiniestro":"Calentador estalló",
       "predio":{"pais":"CO","ciudad":"Bogota","direccion":"Cra 7 # 45-10"},
       "coberturas":[{"codigo":"COB-PLOM","detalle":"Reparar tubería"},
                     {"codigo":"COB-PINT","detalle":"Pintar muro","requiereTerminar":["COB-PLOM"]}]}'
```

Valores permitidos:

- `urgencia`: `Baja`, `Media`, `Alta` o `Emergencia`.
- `categoria`: `Plomeria`, `Electricidad`, `Carpinteria`, `Pintura` o `Baldoseria`.
- filtro `estado`: `Creado`, `EnEjecucion`, `Cerrado` o `Cancelado`.

La API responde `201` al crear (`200` si un partner repite una referencia existente), `200`
en operaciones exitosas, `400` ante datos inválidos o solicitudes de partner intraducibles,
`404` si no existe el trabajo o el partner, y `409` ante transiciones no permitidas,
proveedor fuera de la red, sobrecosto o conflicto de concurrencia.

## Pendientes conocidos

- **Outbox** para garantizar la entrega de eventos y de novedades a partners. Hoy las
  novedades pendientes viven en memoria y se pierden si el proceso se reinicia.
- **Migraciones versionadas** en lugar de `create_all`. Un cambio en `modelos_orm.py` no
  altera tablas existentes.
- **Clientes reales** (HTTP, SOAP, webhooks con timeout) en lugar de `ClientePartnerSimulado`.
- **Validar proveedores contra ProveedoresBC** (ACL downstream del mapa de contextos). Hoy
  `proveedor_id` es un identificador opaco.

## Decisiones arquitectónicas importantes

Cada decisión registra el problema que resuelve, la alternativa descartada y lo que cuesta.
Las que responden directamente a un escenario de calidad lo indican en el título.

### DA-01. Arquitectura hexagonal con DDD táctico y CQS

- **Contexto:** GestionDeTrabajosBC es el core domain y el upstream del que dependen casi
  todos los demás contextos. Sus reglas (flujos con dependencias, novedades, acuerdos) deben
  evolucionar sin arrastrar decisiones de tecnología.
- **Decisión:** el agregado `Trabajo` es la única puerta para cambiar sub-trabajos. Cada caso
  de uso es un comando o una query con su handler, y dominio y aplicación solo conocen
  puertos. Es la misma estructura de WalletBC.
- **Alternativa descartada:** un modelo anémico con la lógica en servicios o rutas. Es más
  rápido de escribir, pero dispersa las reglas y las acopla a la tecnología.
- **Consecuencias:** más archivos y mapeos (schema → comando → DTO), a cambio de poder
  sustituir persistencia, mensajería y partners sin tocar las reglas. Es la base de los
  escenarios #3 y #9.

### DA-02. Capa anti-corrupción con un adaptador por partner, dentro del servicio (escenarios #3 y #9)

- **Contexto:** más de 30 partners, cada uno con formato, reglas y compliance propios. El
  escenario exige que el core no conozca esas particularidades.
- **Decisión:** puerto `AdaptadorDePartner` en la capa de aplicación y un adaptador por
  partner en `acl_partners/`. Cada adaptador traduce en tres sentidos: la solicitud entrante,
  la consulta de estado y las novedades salientes. El módulo vive dentro de
  GestionDeTrabajosBC.
- **Alternativa descartada:** el ACL como bounded context propio, como plantea el escenario 9.
  Da despliegue y escalado independientes, pero agrega un servicio más y un salto de red en
  cada transacción, algo que la POC no necesita.
- **Consecuencias:** los adaptadores se despliegan y escalan junto con el core. La frontera es
  explícita (solo el puerto y el modelo canónico), así que extraer el ACL es mover la carpeta
  y enviar `CrearTrabajoDesdePartnerV1` por Pulsar, comando que el servicio ya acepta.
- **Punto de sensibilidad:** cuánto sabe cada adaptador de las reglas del partner. Aquí solo
  las resuelve a tres valores canónicos (DA-03). Si un adaptador empieza a orquestar pasos
  propios, se convierte en un mini-dominio.

### DA-03. Modelo canónico y acuerdo comercial congelado al crear (escenario #3)

- **Contexto:** cada partner expresa sus reglas a su manera (plan de póliza, nivel SOAP,
  tarifa por país). Si el agregado las conociera, cada partner nuevo obligaría a modificarlo.
- **Decisión:** toda entrada llega como `SolicitudDeTrabajo`, y las reglas se reducen a un
  `AcuerdoComercial` con tope, red de proveedores permitida y SLA. Se guarda con el trabajo y
  no cambia aunque el partner modifique sus reglas después.
- **Alternativa descartada:** consultar las reglas vigentes del partner en cada operación.
  Hace que el core dependa de que el partner esté en línea y altera las condiciones de
  trabajos ya pactados.
- **Consecuencias:** un partner con una regla que no quepa en esos tres valores obliga a
  ampliar el modelo canónico. Es el riesgo aceptado del escenario 3: "un partner con reglas
  muy particulares fuerza a romper la abstracción del puerto".

### DA-04. Traducción todo o nada e idempotencia por referencia del partner (escenario #9)

- **Contexto:** la medida exige que el 100 % de las transacciones se traduzca correctamente,
  y los partners reintentan cuando no reciben respuesta.
- **Decisión:** si un código, plan o servicio no tiene equivalencia, la solicitud completa se
  rechaza con 400 y no se crea nada. La pareja `(partner_id, referencia_externa)` es única en
  la base: repetir una solicitud devuelve el trabajo original con 200.
- **Alternativa descartada:** crear el trabajo con lo que sí se pudo traducir y marcar el resto
  para revisión manual. Deja trabajos inconsistentes frente al contrato del partner.
- **Consecuencias:** un error en la tabla de equivalencias de un adaptador frena las
  solicitudes de ese partner hasta corregirlo, pero nunca produce datos a medias.

### DA-05. Eventos de integración versionados y separados de los de dominio (escenario #9)

- **Contexto:** los consumidores (partners y otros contextos) tienen ciclos de release ajenos
  a HdA; un cambio interno no puede romperlos.
- **Decisión:** clases propias en `eventos_integracion/`, con tipos primitivos y la versión en
  el nombre. Una versión nueva convive con la anterior (`TrabajoCreadoV1`, deprecado, y
  `TrabajoCreadoV2`), ambas con el mismo `event_id`, y cada mensaje lleva `event_version` y
  `deprecado` como propiedades.
- **Alternativa descartada:** publicar el evento de dominio serializado tal cual. Renombrar un
  campo interno rompería a todos los consumidores.
- **Consecuencias:** hay que mantener un traductor por versión. Para evitar el crecimiento
  descontrolado de versiones, la política es mantener como máximo dos activas por evento y
  retirar la deprecada cuando ningún consumidor la lea.

### DA-06. Circuit breaker, hilo y cola por partner (escenario #9)

- **Contexto:** si el core de un partner falla o se pone lento, no puede bloquear el flujo
  interno ni degradar a los demás partners.
- **Decisión:** cada partner tiene su `SincronizadorDePartner`, con circuit breaker propio,
  hilo propio (bulkhead) y cola ordenada de pendientes. Lo que no se entrega queda como
  *sincronización degradada* y se reintenta; al vencer el tiempo de recuperación, el circuito
  prueba de nuevo y entrega en orden.
- **Alternativas descartadas:** un circuit breaker global, porque la caída de un partner
  cortaría a todos; y sincronizar dentro de la petición HTTP, porque un partner lento haría
  lenta la API.
- **Consecuencias:** umbral y tiempo de recuperación deben calibrarse por partner
  (`PARTNER_CB_*`): muy sensible corta tráfico legítimo, muy laxo no protege. Los pendientes
  viven en memoria y se pierden si el proceso se reinicia (ver DA-08).

### DA-07. Apache Pulsar detrás del puerto `MessageBroker`

- **Contexto:** la arquitectura objetivo es orientada a eventos, y el mapa TO-BE nombra a
  Apache Kafka como plataforma.
- **Decisión:** Apache Pulsar, con un tópico de eventos y uno de comandos.
  - Los eventos usan `trabajo_id` como clave de partición: con `Key_Shared`, los hechos de un
    mismo trabajo llegan en orden aunque haya varios consumidores.
  - Los comandos que fallan por causas técnicas se reentregan y, tras tres intentos, pasan a
    una *dead letter queue*.
- **Alternativas descartadas:**
  - Kafka: el equipo eligió Pulsar, y el puerto `MessageBroker` deja la decisión reversible.
  - Un tópico por tipo de evento: multiplica los tópicos, y con propiedades en el mensaje
    cada consumidor filtra sin leer el cuerpo.
- **Consecuencias:** en local, Pulsar standalone consume bastante CPU y memoria. Por eso
  existe el adaptador `logging`, para trabajar sin él.

### DA-08. Publicar después del commit, sin Outbox (por ahora)

- **Contexto:** el estado del agregado y los eventos que publica deben ser coherentes.
- **Decisión:** el caso de uso guarda (commit) y luego despacha los eventos al bus interno.
  Un suscriptor que falla se registra en el log y no afecta a los demás ni a la respuesta,
  con el mismo criterio de WalletBC.
- **Alternativa descartada:** el patrón Outbox, que guarda el evento en la misma transacción y
  lo publica un proceso aparte. Garantiza la entrega, pero agrega infraestructura que la POC
  no requiere.
- **Consecuencias:** si Pulsar o el proceso caen justo después del commit, un evento o una
  novedad pendiente pueden perderse. Es el primer pendiente para producción.

### DA-09. Base de datos propia y bloqueo optimista

- **Contexto:** cada bounded context es dueño de sus datos, y un mismo trabajo puede recibir
  operaciones simultáneas por REST y por comandos de Pulsar.
- **Decisión:** la base `trabajos_db` es exclusiva del servicio y cada trabajo lleva una
  versión. Si otra operación lo guardó entre la lectura y la escritura, se responde 409 (o se
  reentrega el comando).
- **Alternativa descartada:** bloqueo pesimista (`SELECT ... FOR UPDATE`), que retiene las
  filas durante toda la operación.
- **Consecuencias:** ante operaciones concurrentes sobre el mismo trabajo, el cliente puede
  recibir un conflicto y debe reintentar.

### DA-10. Raíz de composición compartida por REST y Pulsar

- **Contexto:** los mismos casos de uso se invocan desde la API REST y desde el consumidor de
  comandos de Pulsar.
- **Decisión:** el cableado de puertos y adaptadores vive en
  `app/infraestructura/contenedor.py` y lo usan ambas entradas, en lugar de quedar en
  `dependencias.py` de la API como en WalletBC.
- **Consecuencias:** un comando produce exactamente los mismos eventos llegue por REST o por
  Pulsar, y una entrada nueva no duplica el cableado.

## Flujo de prueba de los escenarios con Postman

### 1. Preparación

1. Levante el servicio en el puerto 8001. Con Docker, desde la raíz del repositorio:

   ```powershell
   docker compose up -d --build --wait gestion-trabajos
   ```

   Sin Docker, use la opción B de [Requisitos y ejecución](#requisitos-y-ejecución).
2. Deje los logs visibles en otra terminal: `docker compose logs -f gestion-trabajos` (en la
   opción B se ven en la misma consola de `uvicorn`).
3. En Postman, haga **Import** de los dos archivos de `collections/` y seleccione el
   environment **GestionDeTrabajosBC — local**.
4. Compruebe que el servicio responde: el request **Partners integrados y su salud** (carpeta
   02) debe listar `seguros-alpes`, `banco-andino` y `muebles-hogar`, todos con circuito
   `Cerrado`.

### 2. Escenario 9 — Interoperabilidad

> **Estímulo:** los partners B2B2C envían solicitudes en su propio formato y con sus propias
> reglas. **Medida:** el 100 % de las transacciones se traduce al modelo canónico sin
> contaminar el core; ante la falla de un partner, el sistema se recupera automáticamente en
> segundos sin degradar a los demás.

En el **Collection Runner**, seleccione las carpetas **02, 03 y 04** y ejecútelas juntas, en
ese orden: cada una usa variables y estado de la anterior. La corrida tarda unos 20 segundos
por las esperas de la carpeta 03.

**Parte A — Tres formatos distintos entran al mismo core (carpeta 02)**

| # | Request | Resultado esperado | Qué demuestra |
|---|---|---|---|
| 1 | Seguros de los Alpes (REST propio) → crear siniestro | `201`; JSON de la aseguradora con `numeroSiniestro`, `estado: RECIBIDO` y `topePoliza: 4000000` | Traduce su formato y resuelve su regla (tope del plan PLUS) |
| 2 | Seguros → reintento idempotente | `200` con el mismo `idTrabajoHdA` | Un reintento del partner no duplica el trabajo |
| 3 | Seguros → consultar estado con su número | `200`, `RECIBIDO` | El partner consulta con su referencia y su vocabulario |
| 4 | Seguros → vista canónica en HdA | `canal: Partner`, `sla_horas: 24`, pintura `Bloqueado` | El core solo ve el modelo canónico: `requiereTerminar` pasó a ser una dependencia y la prioridad ALTA, un SLA |
| 5 | Banco Andino (SOAP) → crear orden | `201` en `text/xml` con `<ba:Estado>REGISTRADA</ba:Estado>` | Un formato totalmente distinto usa el mismo caso de uso |
| 6 | Banco → consultar estado (SOAP) | `<ba:ActividadesTotales>4</ba:ActividadesTotales>` | Las etapas del SOAP quedaron como sub-trabajos con dependencias |
| 7 | Muebles del Hogar (webhook) → solicitar instalación | `201`, `status: scheduled`, 5 pasos | Un tercer formato: webhook en inglés |
| 8 | Partners integrados y su salud | 3 partners | Cada partner tiene su propio circuito |

**Parte B — Falla de un partner (carpeta 03)**

| # | Request | Resultado esperado | Qué demuestra |
|---|---|---|---|
| 1 | Simular caída del core de Seguros | `core_disponible: false` | Se simula la falla del partner |
| 2 | Asignar proveedor homologado con el partner caído | `200` en menos de 1 s | El flujo interno no se bloquea |
| 3 | Salud de Seguros: sincronización degradada | `pendientes ≥ 1` y `degradaciones ≥ 1` | La novedad no se pierde: queda pendiente |
| 4 | Cancelar la orden del Banco (otro partner) | `200` | Otro partner opera mientras Seguros está caído |
| 5 | Salud del Banco: no se degradó | circuito `Cerrado`, `pendientes: 0`, `sincronizados ≥ 1` | La falla de un partner no degrada a los demás |
| 6 | Restaurar el core de Seguros | `200` | El partner vuelve a estar disponible |
| 7 | Salud de Seguros: recuperación automática | Tras 12 s de espera: `pendientes: 0`, circuito `Cerrado` | Se recupera en segundos sin intervención |

Mientras corre esta carpeta, los logs muestran `sincronizacion_degradada partner=seguros-alpes`
y ninguna degradación para `banco-andino`. Al final aparece
`partner_core=seguros-alpes recibio operacion=PROVEEDOR_ASIGNADO`: la novedad pendiente llegó.

**Parte C — Las reglas del partner se aplican sin que el core las conozca (carpeta 04)**

| Request | Resultado esperado |
|---|---|
| Proveedor fuera de la red homologada → 409 | `409`, y se publica `AsignacionRechazadaV1` |
| Sobrecosto sobre el tope de la póliza → 409 | `409` |
| Solicitud de partner intraducible → 400 | `400` (plan `DORADO` sin equivalencia) y no se crea ningún trabajo |
| Partner no integrado → 404 | `404` |

El resto de la carpeta verifica reglas del flujo: sub-trabajo bloqueado, cierre incompleto,
evidencia obligatoria y dependencias en ciclo.

**Versionado de eventos.** Cada creación deja en los logs `TrabajoCreadoV1` con
`"deprecado": true` y `TrabajoCreadoV2`. Con el servicio en Docker (Pulsar real) también se
puede observar como lo haría un consumidor:

```powershell
cd gestion-trabajos-service
.venv\Scripts\python.exe -m scripts.escuchar_eventos --evento TrabajoCreado
```

**Cómo queda cubierta la medida**

| Medida del escenario | Dónde se observa |
|---|---|
| Se traduce al modelo canónico sin contaminar el core | 02.1, 02.4, 02.5 y 02.7 |
| El 100 % de las transacciones se traduce correctamente | 02.2 (idempotencia) y 04 "intraducible" (todo o nada) |
| Si el partner falla, no bloquea el flujo interno | 03.2 |
| Se recupera automáticamente en segundos | 03.7 |
| No degrada a los otros partners | 03.5 |

### 3. Escenario 3 — Modificabilidad

> **Estímulo:** se incorpora un partner nuevo con sus propias reglas y su propio flujo.
> **Medida:** 0 % de componentes del dominio de GestionDeTrabajosBC modificados.

Se usa la carpeta **05** en dos momentos, con un cambio de código en medio. No la ejecute
junto con las demás carpetas.

**Paso 1 — Antes del onboarding.** Ejecute la subcarpeta **05.1**:

| Request | Resultado esperado |
|---|---|
| Cooperativa Sur todavía no está integrada → 404 | `404`: "El partner 'cooperativa-sur' no está integrado con HdA" |
| Partners integrados (sin la cooperativa) | La lista no incluye `cooperativa-sur` |

**Paso 2 — Integrar el partner tocando solo infraestructura.** Desde
`gestion-trabajos-service`:

1. Copie el adaptador de ejemplo a la carpeta de adaptadores:

   ```powershell
   Copy-Item ejemplos\onboarding\cooperativa_sur.py app\infraestructura\adaptadores\acl_partners\
   ```

2. Regístrelo en `app/infraestructura/adaptadores/acl_partners/registro.py` agregando las
   dos líneas marcadas:

   ```python
   from .banco_andino import BancoAndinoAdapter
   from .cooperativa_sur import CooperativaSurAdapter      # nueva
   from .muebles_hogar import MueblesHogarAdapter
   from .seguros_alpes import SegurosAlpesAdapter

   ADAPTADORES_REGISTRADOS = (
       SegurosAlpesAdapter,
       BancoAndinoAdapter,
       MueblesHogarAdapter,
       CooperativaSurAdapter,                              # nueva
   )
   ```

3. Aplique el cambio:
   - **En Docker:** desde la raíz del repositorio, ejecute
     `docker compose up -d --build --wait gestion-trabajos`. Reconstruir la imagen es
     obligatorio: reiniciar el contenedor no basta.
   - **En local:** detenga `uvicorn` con Ctrl+C y vuelva a iniciarlo.

**Paso 3 — Después del onboarding.** Ejecute la subcarpeta **05.2**:

| Request | Resultado esperado | Qué demuestra |
|---|---|---|
| Partners integrados (con la cooperativa) | `cooperativa-sur` aparece con circuito `Cerrado` | El partner nuevo obtiene su circuit breaker sin escribirlo |
| Cooperativa Sur crea una orden en texto plano → 201 | `201`, `text/plain`, contenido con `\|RECIBIDA\|0/3\|` | El mismo request que antes daba 404, ahora en un cuarto formato |
| Reintento de la misma orden → 200 | `200` | La idempotencia la da el caso de uso genérico |
| Vista canónica en HdA | `Partner`, `AR`, `ARS`, `sla_horas: 24`; plomería `Pendiente`, electricidad y pintura `Bloqueado` | `PLOM>ELEC+PINT` se volvió un flujo canónico sin cambiar el agregado `Trabajo` |
| La cooperativa consulta con su referencia | `200`, `RECIBIDA` | Responde en el formato del partner |

**Paso 4 — Verificar la medida.** Desde `gestion-trabajos-service`:

```powershell
git status --short app
git diff --stat -- app/dominio app/aplicacion
```

El primer comando solo muestra `acl_partners/cooperativa_sur.py` (nuevo) y
`acl_partners/registro.py` (modificado). El segundo sale vacío: 0 % de componentes del
dominio modificados.

> Estos comandos comparan contra el último commit, así que el servicio debe estar versionado
> en git antes de hacer el onboarding.

**Paso 5 — Repetir la demostración.** Borre
`app/infraestructura/adaptadores/acl_partners/cooperativa_sur.py`, quite las dos líneas de
`registro.py` y vuelva a aplicar el cambio como en el paso 2.3.
