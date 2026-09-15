# OperacionesBC — Partners B2B2C y capa anti-corrupción

Microservicio de Hogar de los Alpes que concentra la relación con los partners B2B2C
(aseguradoras, bancos y comercios):

- **Acuerdos comerciales:** registra a cada partner con su acuerdo (topes, SLA y red de
  proveedores homologados).
- **Solicitudes:** recibe las solicitudes de trabajo en el formato propio de cada partner, las
  traduce al modelo canónico y le pide a **GestionDeTrabajosBC** que cree el trabajo.
- **Novedades:** mantiene la vista de los trabajos de cada partner y le entrega las novedades en su
  formato, con un circuit breaker por partner.

Es el artefacto del escenario de Modificabilidad #3 ("adaptador de entrada — Anti-Corruption
Layer — para el nuevo partner en OperacionesBC") y de la capa de integración del escenario de
Interoperabilidad #9.

GestionDeTrabajosBC y OperacionesBC **no se llaman entre sí**:

- OperacionesBC envía el comando `CrearTrabajoV1` por Apache Pulsar.
- GestionDeTrabajosBC publica sus eventos, y OperacionesBC los consume. Al agregado `Trabajo`
  solo lo referencia por su identificador.

> En el mapa de contextos TO-BE, el motor de reglas por partner aparece en SiniestrosBC y la
> relación comercial en OperacionesBC. Esta implementación sigue el escenario #3 y su diagrama:
> el acuerdo y la capa de integración viven en OperacionesBC. El mapa debe actualizarse para
> reflejarlo.

## Arquitectura

```
operaciones-service/
├── Dockerfile
├── requirements.txt
├── .env.example
├── collections/                  # Colección Postman de los escenarios de calidad
├── ejemplos/onboarding/          # Partner listo para demostrar el onboarding (no registrado)
└── app/
    ├── seedwork/                 # Entity, ValueObject, AggregateRoot, DomainEvent, CircuitBreaker...
    ├── dominio/
    │   ├── partner/              # Partner «Agregado», AcuerdoComercial y CondicionComercial «ObjetoValor»
    │   └── errores/
    ├── aplicacion/
    │   ├── comandos/             # RegistrarPartner, CrearTrabajoDesdePartner, ProcesarEventoDeTrabajo
    │   ├── queries/              # ListarPartners, ObtenerPartner, ConsultarTrabajoDePartner
    │   ├── puertos/              # AdaptadorDePartner, CatalogoDeAdaptadores, GestionDeTrabajos, TrabajosDePartnerRepository
    │   ├── proyeccion.py         # eventos de GestionDeTrabajosBC → vista del trabajo del partner
    │   └── dtos/
    └── infraestructura/
        ├── contenedor.py         # raíz de composición compartida por REST y Pulsar
        ├── semilla.py            # partners con acuerdo vigente al iniciar la POC
        └── adaptadores/
            ├── entrada/api/      # FastAPI: acuerdos y solicitudes de partners
            ├── entrada/mensajeria/  # consumidor de eventos de GestionDeTrabajosBC
            ├── salida/gestion_de_trabajos/  # envía CrearTrabajoV1 por Pulsar
            ├── salida/persistencia/          # partners y vista de trabajos
            └── acl_partners/     # un adaptador por formato + sincronización resiliente
```

Sigue la misma arquitectura de los demás servicios: DDD, hexagonal y CQS. `app/dominio` y
`app/aplicacion` no importan infraestructura. Los adaptadores de partner solo traducen
formato: las reglas comerciales viven en el dominio.

## Modelo de dominio

| Concepto | En el código |
|---|---|
| Partner | Agregado `Partner`: identificador (`seguros-alpes`), nombre, país y acuerdo vigente |
| Acuerdo comercial | Objeto valor `AcuerdoComercial`: condiciones y red de proveedores homologados |
| Condición comercial | Objeto valor `CondicionComercial`: para una clave que el partner reconoce (plan, prioridad, país), un `TOPE` de costo o un `SLA` en horas |
| Condiciones aplicables | Objeto valor `CondicionesAplicables`: tope, red y SLA resueltos para una solicitud; es lo único que viaja a GestionDeTrabajosBC |

Reglas:

- **Claves pactadas:** una solicitud que menciona una clave no pactada (por ejemplo, un plan de
  póliza inexistente) se rechaza con 400 y no llega a GestionDeTrabajosBC.
- **Tope autorizado:** si el partner autoriza un tope en la propia solicitud (el banco lo hace
  por orden), no puede superar lo pactado; si lo supera, 409.
- **Renegociación:** renegociar un acuerdo (`PUT /partners/{id}`) no altera los trabajos ya
  solicitados, porque GestionDeTrabajosBC guardó las condiciones vigentes al crearlos.

## Colaboración con GestionDeTrabajosBC

```mermaid
sequenceDiagram
    participant P as Partner
    participant O as OperacionesBC
    participant PU as Apache Pulsar
    participant T as GestionDeTrabajosBC
    P->>O: POST /partners/{id}/trabajos (formato propio)
    O->>O: el adaptador traduce y el Partner resuelve las condiciones
    O->>PU: CrearTrabajoV1 (comandos-trabajo)
    O-->>P: 202 en el formato del partner
    PU->>T: CrearTrabajoV1
    T->>PU: TrabajoCreadoV2 o CreacionDeTrabajoRechazadaV1 (eventos-trabajo)
    PU->>O: evento con partner_id
    O->>O: actualiza la vista del trabajo
    O-->>P: novedad en su formato (circuit breaker por partner)
    P->>O: GET /partners/{id}/trabajos/{referencia}
    O-->>P: estado en su formato
```

- **Creación asíncrona:** la solicitud responde 202. El trabajo aparece en la vista del partner
  cuando llega `TrabajoCreadoV2`, normalmente en menos de un segundo.
- **Rechazos:** si GestionDeTrabajosBC no puede crear el trabajo (por ejemplo, una cobertura
  que exige otra que no viene), publica `CreacionDeTrabajoRechazadaV1` y el partner lo ve como
  rechazo con su motivo.
- **Envío con confirmación:** el comando espera la confirmación de Pulsar. Si Pulsar no lo
  recibe, el partner obtiene 503 y puede reintentar. Reintentar la misma referencia nunca crea
  dos trabajos.

## Partners integrados

| `partner_id` | Formato | Claves de su acuerdo | Novedades que recibe |
|---|---|---|---|
| `seguros-alpes` | REST con JSON propio | Tope por plan (BASICO 1,5 M · PLUS 4 M · PREMIUM 10 M COP), SLA por prioridad, red homologada | Proveedor asignado, cambio de alcance, anulación, cierre, rechazo |
| `banco-andino` | SOAP (XML), México | Tope `ORDEN` 50.000 MXN (la orden autoriza uno menor o igual), SLA por nivel 1–4 | Conclusión, cancelación, cotización rechazada, orden rechazada |
| `muebles-hogar` | Webhooks JSON | Tope por país (CO/MX), SLA standard/express | Paso completado, reprogramación, cancelación, cierre, rechazo |

Cada adaptador documenta su formato con un ejemplo en su archivo. Los cores de los partners
se simulan con `ClientePartnerSimulado`, que registra lo recibido en el log y permite simular
caídas.

### Integrar un partner nuevo

1. **Onboarding contractual, sin código:** registrar el acuerdo con
   `PUT /partners/{partner_id}`, como en
   [`ejemplos/onboarding/acuerdo_cooperativa_sur.json`](ejemplos/onboarding/acuerdo_cooperativa_sur.json).
2. **Integración técnica, solo en OperacionesBC:** escribir el adaptador en
   `app/infraestructura/adaptadores/acl_partners/`, agregarlo a `ADAPTADORES_REGISTRADOS` en
   `registro.py` y reconstruir OperacionesBC.

GestionDeTrabajosBC no se modifica ni se redespliega. El partner listo para demostrarlo está en
[`ejemplos/onboarding/cooperativa_sur.py`](ejemplos/onboarding/cooperativa_sur.py).

## Ejecución

El flujo completo necesita GestionDeTrabajosBC y Apache Pulsar. Desde la raíz del
repositorio:

```bash
docker compose up -d --build --wait gestion-trabajos operaciones
```

- OperacionesBC queda en <http://localhost:8002/docs> y GestionDeTrabajosBC en
  <http://localhost:8001/docs>.
- Logs: `docker compose logs -f operaciones gestion-trabajos`.
- Detener sin borrar datos: `docker compose stop`.

Sin Docker, OperacionesBC arranca con SQLite y `MESSAGE_BROKER=logging`. Sirve para probar
acuerdos y traducciones: el comando `CrearTrabajoV1` solo se escribe en el log y los trabajos
no llegan a crearse.

```powershell
cd operaciones-service
python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt
New-Item -ItemType Directory -Force app\data
$env:DATABASE_URL="sqlite+pysqlite:///./app/data/operaciones.db"
$env:MESSAGE_BROKER="logging"
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --port 8002
```

### Configuración

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://operaciones:operaciones@localhost:5434/operaciones_db` | Conexión a la base |
| `MESSAGE_BROKER` | `logging` | `pulsar` o `logging` |
| `PULSAR_URL` | `pulsar://localhost:6650` | Broker de Pulsar |
| `PULSAR_TOPICO_COMANDOS_TRABAJO` / `PULSAR_TOPICO_EVENTOS_TRABAJO` | `comandos-trabajo` / `eventos-trabajo` | Tópicos de GestionDeTrabajosBC |
| `PULSAR_SUSCRIPCION_EVENTOS` | `operaciones-bc` | Suscripción `Key_Shared` a los eventos de trabajo |
| `PULSAR_CONSUMIR_EVENTOS` | `false` | Arranca el consumidor de eventos |
| `SEMBRAR_PARTNERS` | `true` | Registra al iniciar los partners con acuerdo vigente |
| `PARTNER_CB_UMBRAL_FALLOS` | `3` | Fallos consecutivos que abren el circuito de un partner |
| `PARTNER_CB_RECUPERACION_SEGUNDOS` | `10` | Tiempo con el circuito abierto antes de probar de nuevo |
| `PARTNER_SINCRONIZACION_ASINCRONA` | `true` | Entrega a los partners en hilos propios |

## API REST

| Método y ruta | Descripción |
|---|---|
| `GET /partners` | Partners, su acuerdo y si ya tienen adaptador |
| `GET /partners/{partner_id}` | Acuerdo de un partner |
| `PUT /partners/{partner_id}` | Registra el partner con su acuerdo (201) o lo renegocia (200) |
| `POST /partners/{partner_id}/trabajos` | Solicitud de trabajo en el formato del partner: 202 (nueva) o 200 (referencia existente) |
| `GET /partners/{partner_id}/trabajos/{referencia}` | Estado del trabajo en el formato del partner |
| `GET /partners/{partner_id}/salud` | Circuito, pendientes y degradaciones de la sincronización |
| `PUT /partners/{partner_id}/simulacion` | Simula la caída o recuperación del core del partner |

Códigos:

- `202` o `200`: solicitud aceptada.
- `400`: formato intraducible o condición no pactada.
- `404`: partner no registrado, sin adaptador o referencia inexistente.
- `409`: tope autorizado mayor al pactado.
- `503`: no se pudo entregar la solicitud a GestionDeTrabajosBC.

## Decisiones arquitectónicas importantes

### DO-01. Capa anti-corrupción en su propio bounded context (escenarios #3 y #9)

- **Contexto:** más de 30 partners con formatos, reglas y compliance propios. Integrar uno nuevo
  no debe tocar ni redesplegar el motor de trabajos que ya sirve a los demás.
- **Decisión:** los adaptadores, el caso de uso `CrearTrabajoDesdePartner` y los acuerdos
  comerciales viven en OperacionesBC. Se comunica con GestionDeTrabajosBC solo por Pulsar.
- **Alternativa descartada:** ubicar la capa dentro de GestionDeTrabajosBC. Ahorra un servicio,
  pero cada partner nuevo obliga a redesplegar el core.
- **Consecuencias:** un servicio y una base más, y un salto de mensajería por solicitud. A cambio,
  el onboarding solo reconstruye OperacionesBC y la carga de integraciones escala por separado.
- **Punto de sensibilidad:** cuánto sabe cada adaptador de las reglas del partner. Aquí solo
  traduce formato y señala claves; las reglas son datos del acuerdo (DO-02).

### DO-02. Reglas del partner como datos del agregado `Partner` (escenario #3)

- **Contexto:** cada partner expresa sus reglas a su manera (plan de póliza, nivel de urgencia,
  país).
- **Decisión:** el `AcuerdoComercial` guarda condiciones `TOPE` o `SLA` por clave, y el adaptador
  solo dice qué clave menciona cada solicitud. El acuerdo se registra y renegocia por API.
- **Alternativa descartada:** tablas de reglas dentro de cada adaptador. Mezcla formato y negocio,
  y renegociar exige desplegar código.
- **Consecuencias:** una regla que no se exprese como tope o SLA por clave obliga a ampliar el
  modelo del acuerdo. Es el riesgo "un partner con reglas muy particulares fuerza a romper la
  abstracción del puerto".

### DO-03. Comunicación asíncrona y vista con consistencia eventual (escenario #9)

- **Contexto:** los partners generan millones de solicitudes y el core no debe depender de su
  disponibilidad, ni ellos de la del core.
- **Decisión:** la solicitud se responde con 202 después de publicar `CrearTrabajoV1`, y la vista
  del partner se construye con los eventos de GestionDeTrabajosBC (suscripción `Key_Shared`, orden
  por trabajo).
- **Alternativa descartada:** llamar por REST a GestionDeTrabajosBC en cada solicitud. Da una
  respuesta inmediata, pero acopla la disponibilidad de ambos servicios.
- **Consecuencias:** justo después de solicitar, el trabajo aparece sin `idTrabajoHdA`. Los errores
  de creación llegan como `CreacionDeTrabajoRechazadaV1`, no en la respuesta HTTP.

### DO-04. Traducción todo o nada e idempotencia por referencia (escenario #9)

- **Decisión:** si algo de la solicitud no tiene equivalencia, se rechaza completa. La misma
  referencia del partner no vuelve a solicitarse, salvo que haya sido rechazada. GestionDeTrabajosBC
  además crea un solo trabajo por referencia.
- **Consecuencias:** los reintentos de partners, de Pulsar o de OperacionesBC nunca duplican
  trabajos.

### DO-05. Circuit breaker, hilo y cola por partner (escenario #9)

- **Decisión:** cada partner tiene su `SincronizadorDePartner`, con breaker, hilo y cola ordenada
  de pendientes propios. Lo que falla queda como *sincronización degradada* y se entrega al
  recuperarse el circuito.
- **Alternativas descartadas:**
  - un breaker global, porque la caída de uno cortaría a todos;
  - entregar dentro del consumidor de eventos, porque un partner lento frenaría la vista de los
    demás.
- **Consecuencias:** umbral y tiempo de recuperación deben calibrarse por partner. Los pendientes
  viven en memoria y se pierden si el proceso se reinicia (Outbox pendiente).

## Flujo de prueba de los escenarios con Postman

La colección [`collections/EscenariosDeCalidad.postman_collection.json`](collections/README.md)
prueba ambos escenarios contra los dos servicios. El detalle de cada request, con su resultado
esperado, está en [`collections/README.md`](collections/README.md).

1. **Preparar:**
   - levante todo con `docker compose up -d --build --wait gestion-trabajos operaciones`;
   - importe los dos archivos de `collections/` y seleccione el environment
     **Escenarios de calidad — local**.
2. **Interoperabilidad #9:** ejecute las carpetas **01 a 04** juntas con el Collection Runner.
   Cubren la traducción de tres formatos, la caída de un partner sin afectar al core ni a los
   otros partners, la recuperación automática, y las reglas y rechazos del acuerdo.
3. **Modificabilidad #3:**
   1. Ejecute **05.1**: el partner no existe.
   2. Ejecute **05.2**: registre su acuerdo por API; sin adaptador sigue sin integrarse.
   3. Copie `ejemplos/onboarding/cooperativa_sur.py` a `acl_partners/`, regístrelo en
      `registro.py` y ejecute `docker compose up -d --build --wait operaciones`.
   4. Ejecute **05.3**: la orden en texto plano crea el trabajo en GestionDeTrabajosBC.
   5. Compruebe que GestionDeTrabajosBC no se modificó ni se reinició: `git status` no muestra
      cambios en `gestion-trabajos-service/`, y `docker compose ps gestion-trabajos` muestra el
      mismo tiempo de actividad que antes.

## Pendientes conocidos

- **Outbox** para garantizar la entrega de comandos y de novedades a partners.
- **Migraciones versionadas** en lugar de `create_all`.
- **Clientes reales** (HTTP, SOAP, webhooks con timeout) en lugar de `ClientePartnerSimulado`.
