# WalletBC — Billetera de proveedores

Microservicio backend de **Hogar de los Alpes** para crear billeteras, acreditar y debitar
saldo, consultar movimientos y atender los retiros del proveedor.

Es además el **último participante de la Saga de Activación de Servicio**: consume por
Apache Pulsar el comando `AcreditarProveedorV1` que emite el orquestador en
GestionDeTrabajosBC y responde con `WalletAcreditadaV1` o, si la acreditación no prospera
ni después de reintentar, con `AcreditacionFallidaV1`. Ese segundo evento no dispara una
compensación: el trabajo ya se ejecutó, así que pasa a `EN_DISPUTA` para revisión manual
(ver [Participación en la Saga](#participación-en-la-saga)).

## Arquitectura

El código del servicio vive bajo el paquete `app/`, y junto a él quedan los archivos
propios del microservicio:

```
wallet-service/
├── README.md
├── requirements.txt
├── .env.example
├── collections/                  # Colección Postman de WalletBC
├── tests/                        # Unidad de Trabajo y paso de acreditación de la saga
└── app/
    ├── seedwork/
    │   ├── dominio/              # Entity, ValueObject, AggregateRoot, DomainEvent
    │   ├── aplicacion/           # DomainEventHandler, IntegrationEvent
    │   └── infraestructura/      # PoliticaDeReintentos (backoff exponencial)
    ├── dominio/
    ├── aplicacion/
    │   ├── comandos/  queries/  dtos/
    │   ├── puertos/              # UnidadDeTrabajo, DomainEventDispatcher, MessageBroker
    │   ├── manejadores/          # suscriptores del bus + traductores
    │   └── eventos_integracion/  # contrato público versionado
    └── infraestructura/
        ├── configuracion.py
        ├── contenedor.py         # raíz de composición compartida por REST y Pulsar
        ├── semilla.py            # billeteras de demostración creadas al arrancar
        └── adaptadores/
            ├── entrada/
            │   ├── api/          # main.py: crear_app() y la instancia ASGI
            │   └── mensajeria/   # consumidor de comandos de saga en Pulsar
            └── salida/           # persistencia/  eventos/  mensajeria/
```

La implementación sigue DDD, arquitectura hexagonal y CQS:

- `app/seedwork/`: bloques de construcción genéricos, sin conocimiento del negocio. No
  pertenece a ninguna capa porque las tres lo consumen; `seedwork/dominio/` aporta
  `Entity`, `ValueObject`, `AggregateRoot`, `DomainEvent` y `DomainError`,
  `seedwork/aplicacion/` las bases `DomainEventHandler` e `IntegrationEvent`, y
  `seedwork/infraestructura/` la `PoliticaDeReintentos`.
- `app/dominio/`: Python puro. Contiene `Billetera` como agregado raíz, `Movimiento` como
  entidad, objetos valor, fábrica, errores, eventos y el puerto del repositorio.
- `app/aplicacion/`: comandos y queries con un handler dedicado, DTOs `dataclass`, los
  puertos `UnidadDeTrabajo`, `DomainEventDispatcher` y `MessageBroker`, los handlers
  suscritos al bus y el contrato de eventos de integración. No importa FastAPI, Pydantic
  ni SQLAlchemy.
- `app/infraestructura/contenedor.py`: raíz de composición. Decide qué adaptador hay
  detrás de cada puerto y la comparten las dos entradas del servicio, de modo que una
  acreditación produce los mismos efectos llegue por REST o por Pulsar.
- `app/infraestructura/adaptadores/entrada/api/`: rutas FastAPI, schemas Pydantic y mappers.
- `app/infraestructura/adaptadores/entrada/mensajeria/`: consumidor de los comandos de la
  saga.
- `app/infraestructura/adaptadores/salida/`: repositorio SQLAlchemy/PostgreSQL, unidad de
  trabajo, bus interno de eventos y adaptadores de mensajería.

### Unidad de Trabajo (Unit of Work)

La transacción la gobierna el caso de uso, no el repositorio:

- el handler abre el bloque `with self._uow as uow:`, opera sobre `uow.billeteras` y
  confirma al final con `uow.confirmar()`;
- `SqlAlchemyBilleteraRepository` solo hace `flush()`: ya no confirma ni revierte;
- si algo falla antes de confirmar, `SqlAlchemyUnidadDeTrabajo` revierte al salir del
  bloque, de modo que **nunca queda un saldo sin su movimiento ni un movimiento sin su
  saldo** — que es la razón de aplicar el patrón a una billetera;
- el evento de integración se **encola dentro** del bloque (`uow.eventos_salientes`), así
  que entra en el mismo `commit` que el saldo; los eventos de dominio se anuncian al bus
  interno **después** de confirmar, cuando el hecho ya es definitivo (ver la bandeja de
  salida, más abajo);
- se crea una unidad de trabajo por petición HTTP y otra por mensaje de Pulsar, cada una
  con su propia sesión. Las consultas siguen usando un repositorio de solo lectura.

## Participación en la Saga

| Tópico | Dirección | Contenido |
|---|---|---|
| `persistent://public/default/comandos-wallet` | Consume (suscripción `wallet-saga-comandos`, `Shared`) | `AcreditarProveedorV1` |
| `persistent://public/default/eventos-wallet` | Publica | `WalletAcreditadaV1`, `AcreditacionFallidaV1` |

> El documento de arquitectura nombra el comando `AcreditarProveedor` y los eventos
> `WalletAcreditada` / `AcreditacionFallida`. En el bus viajan con sufijo de versión, como
> el resto de contratos del sistema; el consumidor acepta ambas formas.

Flujo de una acreditación:

```
AcreditarProveedorV1 (Pulsar)
  └─ ProcesadorComandosSagaWallet.acreditar_proveedor
       └─ PoliticaDeReintentos (backoff exponencial)
            └─ with unidad_de_trabajo() as uow:      ← transacción local
                 ├─ resolver la billetera del proveedor
                 ├─ ¿ya hay un movimiento con esta saga? → no acreditar dos veces
                 ├─ Billetera.acreditar_liquidacion(...)  ← exige billetera activa
                 └─ uow.confirmar()
       ├─ éxito   → WalletAcreditadaV1
       └─ fallo   → AcreditacionFallidaV1 (requiere_revision_manual)
```

Tres decisiones del paso:

- **Idempotencia.** Cada acreditación se registra con la referencia
  `saga:{saga_id}:acreditacion`. Si Pulsar reentrega el comando, el movimiento ya existe y
  el saldo no se toca; se responde igual con `WalletAcreditadaV1`.
- **Reintentos con backoff.** Un fallo que puede resolverse solo —billetera bloqueada que
  se reactiva, caída puntual de la base o de la pasarela interna— se reintenta hasta
  `ACREDITACION_INTENTOS` veces, esperando `0,5 s`, `1 s`, `2 s`… Un fallo que no depende
  del tiempo (el proveedor no tiene billetera, la moneda no corresponde, el monto es
  inválido) no se reintenta: solo retrasaría la disputa.
- **Política `EN_DISPUTA`.** Agotados los reintentos se emite `AcreditacionFallidaV1` y
  **el trabajo no se revierte**: el servicio ya se prestó. El orquestador marca el trabajo
  `EN_DISPUTA` para que Operaciones lo resuelva a mano.

El consumidor confirma (*ack*) el mensaje en los dos desenlaces, porque en ambos el
procesador ya agotó su política de reintentos y reentregar el comando no cambiaría el
resultado.

`Billetera.acreditar_liquidacion` es el método que usa este paso (y el evento externo
`TrabajoLiquidado`): a diferencia de `acreditar`, **exige la billetera activa**. Una
billetera suspendida rechaza la liquidación con `AcreditacionRechazada` sin mover el saldo.
El `POST /billeteras/{id}/acreditar` administrativo conserva su comportamiento anterior.

## Eventos de dominio y de integración: la bandeja de salida (patrón Outbox)

Un hecho de WalletBC tiene dos destinos con garantías distintas, y por eso viaja por dos
caminos separados:

```
Handler de comando
  └─ with uow:
       ├─ uow.billeteras.guardar(billetera)              flush
       ├─ encolar_eventos_pendientes(billetera, uow)     flush  ← traduce y encola
       │    └─ traductores.py: SaldoDebitado → SaldoDebitadoV1
       │         └─ uow.eventos_salientes.encolar(...)   tabla `eventos_salientes`
       └─ uow.confirmar()                                UN SOLO COMMIT
  └─ anunciar_hechos(hechos, dispatcher)                 tras confirmar
       └─ AuditarEventoDeDominioHandler                  lógica interna del proceso

PublicadorOutbox  (hilo de fondo, cada segundo)
  └─ tomar_pendientes()            SELECT … FOR UPDATE SKIP LOCKED
  └─ MessageBroker.publicar(sobre) ← puerto abstracto, envío síncrono
  │    └─ PulsarMessageBroker | LoggingMessageBroker | InMemoryMessageBroker
  └─ marcar_publicado() | marcar_fallido()   backoff exponencial
```

Cuatro decisiones importantes:

- **El anuncio se guarda con el saldo, en la misma transacción.** La fila de
  `eventos_salientes` y el movimiento entran en el mismo `commit`, así que es imposible
  que exista uno sin el otro. Esa es toda la idea del patrón: antes, el evento se
  publicaba después del commit y una caída del broker en esa ventana lo perdía en
  silencio.
- **Publicar es de otro, y después.** El relay corre fuera de la transacción y puede
  reintentar cuantas veces haga falta sin arriesgar el saldo. A cambio la entrega es
  *at-least-once*: el sobre lleva `event_id` para que el consumidor deduplique.
- **Los eventos de integración son clases aparte** (`aplicacion/eventos_integracion/`),
  con sufijo de versión y campos primitivos. El contrato público no es un volcado del
  evento de dominio, así que renombrar un campo interno no rompe a otros bounded contexts.
  La conversión vive en un solo sitio: `aplicacion/manejadores/traductores.py`, y se
  ejecuta **al encolar**: lo que se guarda ya es contrato público, de modo que un evento
  encolado antes de un despliegue sale con el contrato con el que se guardó.
- **El bus interno ya no publica hacia afuera.** Antes el `PublicarEventoDeIntegracionHandler`
  colgaba del dispatcher junto a la auditoría; se separaron porque tienen garantías
  incompatibles: la auditoría puede perderse sin consecuencias, el contrato público no.
  El dispatcher conserva su aislamiento de suscriptores (un handler roto no arrastra a los
  demás), que ahora solo afecta a lógica interna.

`DebitoRechazado` y `AcreditacionRechazada` se encolan aunque su transacción se haya
revertido: el saldo no se movió, pero el hecho ocurrió. Como no hay nada con lo que ser
atómico, `registrar_hechos()` abre una transacción corta solo para la bandeja. En el caso
de la acreditación, el rechazo se anuncia una sola vez: el definitivo, cuando ya se
agotaron los reintentos.

### Operar la bandeja

| Endpoint | Uso |
|---|---|
| `GET /outbox/resumen` | Conteo por estado. Si `por_publicar` crece, el broker no está recibiendo |
| `GET /outbox?estado=PENDIENTE` | Detalle de los eventos, con intentos y último error |
| `POST /outbox/{event_id}/reencolar` | Devuelve a la cola un evento `FALLIDO` |

Estados de una fila: `PENDIENTE` → `PUBLICADO`, o `PENDIENTE` → `FALLIDO` cuando se agotan
los `OUTBOX_MAX_INTENTOS`. `FALLIDO` es terminal *para el relay*, no para el operador: la
fila conserva su payload y se puede reencolar.

Con varias réplicas del servicio, `tomar_pendientes` usa `FOR UPDATE SKIP LOCKED` en
PostgreSQL, así que cada relay se lleva filas distintas y ninguna se publica dos veces.
SQLite no soporta la cláusula y tampoco la necesita.

### DW-01. Bandeja de salida transaccional en lugar de publicar tras el commit

- **Contexto:** WalletBC mueve dinero. Publicar el evento después de confirmar deja una
  ventana en la que el saldo cambió y el anuncio se perdió —basta con que el broker esté
  caído en ese instante—, y nadie se entera: no hay excepción ni rastro. En un contexto
  financiero, un saldo acreditado que el resto del ecosistema nunca conoce es una
  inconsistencia silenciosa.
- **Decisión:** el caso de uso traduce el hecho a contrato público y lo **encola en
  `eventos_salientes` dentro de su propia transacción**. Un relay en un hilo de fondo lee
  lo pendiente y lo publica, reintentando con backoff exponencial. El puerto
  `MessageBroker` pasa a recibir un `SobreDeEvento` ya serializado y a exigir envío
  síncrono, porque el relay solo puede marcar una fila como publicada si tiene la
  confirmación del broker.
- **Alternativa descartada:** dejar la publicación colgando del bus de eventos de dominio
  (como estaba) y confiar en que Pulsar esté disponible. Es una línea de código y cero
  tablas, pero la garantía que ofrece es «casi siempre», que es precisamente lo que no
  sirve para una billetera. También se descartó publicar *antes* de confirmar: anunciaría
  acreditaciones que luego se revierten.
- **Consecuencias:** una tabla y un hilo más por proceso, latencia de hasta
  `OUTBOX_INTERVALO_SEGUNDOS` entre el hecho y su anuncio, y entrega *at-least-once* —el
  consumidor debe deduplicar por `event_id`—. A cambio, ningún evento confirmado se pierde
  aunque el broker esté caído: se acumulan en `PENDIENTE` y salen cuando vuelve.
- **Punto de sensibilidad:** el crecimiento de la tabla. Hoy las filas `PUBLICADO` se
  conservan porque sirven de auditoría y el volumen de la POC es bajo; en producción
  necesitan una purga periódica.

## Requisitos y ejecución

Se necesita Python 3.11 o posterior. Docker es opcional: la aplicación puede ejecutarse
con PostgreSQL en Docker, con una instalación local de PostgreSQL o con SQLite.

Todos los comandos se ejecutan desde el directorio del microservicio. Primero instale
las dependencias:

```bash
cd hogar-de-los-alpes/wallet-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Configuración

La conexión se toma de `DATABASE_URL`. Copie la plantilla y ajuste sus credenciales:

```bash
cp .env.example .env
```

| Variable | Por defecto | Uso |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db` | Conexión a la base |
| `PULSAR_URL` | `pulsar://localhost:6650` | Broker de Pulsar |
| `PULSAR_CONSUMIR_COMANDOS_WALLET` | `false` | Arranca el consumidor de comandos de la saga |
| `PULSAR_TOPICO_COMANDOS_WALLET` / `PULSAR_TOPICO_EVENTOS_WALLET` | `comandos-wallet` / `eventos-wallet` | Tópicos de la saga |
| `PULSAR_SUSCRIPCION_COMANDOS_WALLET` | `wallet-saga-comandos` | Suscripción del consumidor |
| `ACREDITACION_INTENTOS` | `3` | Intentos antes de declarar la disputa |
| `ACREDITACION_ESPERA_INICIAL_SEGUNDOS` | `0.5` | Primera espera del backoff |
| `ACREDITACION_FACTOR_BACKOFF` | `2.0` | Cuánto crece la espera en cada intento |
| `SEMBRAR_BILLETERAS` | `true` | Crea al arrancar la billetera del proveedor de la demo |
| `MESSAGE_BROKER` | `logging` | Transporte del relay: `pulsar` o `logging` |
| `PULSAR_TOPICO_EVENTOS_INTEGRACION` | `eventos-wallet-integracion` | Tópico al que publica la bandeja de salida |
| `OUTBOX_HABILITADO` | `true` | Arranca el relay. En `false` los eventos se encolan y nadie los publica |
| `OUTBOX_INTERVALO_SEGUNDOS` | `1.0` | Cada cuánto el relay busca pendientes |
| `OUTBOX_LOTE` | `50` | Máximo de eventos por pasada |
| `OUTBOX_MAX_INTENTOS` | `5` | Intentos de entrega antes de marcar `FALLIDO` |
| `OUTBOX_ESPERA_BASE_SEGUNDOS` | `2.0` | Primera espera del backoff del relay |

Sin Pulsar el servicio arranca igual: la API REST sigue atendiendo billeteras y retiros, y
solo deja de llegar el paso de acreditación de la saga. Los eventos de integración se
siguen encolando en la bandeja de salida y saldrán cuando el broker vuelva.

### Pruebas automatizadas

Cubren la Unidad de Trabajo (confirmación, reversión y atomicidad saldo/movimiento), el
retiro por proveedor, el paso de acreditación de la saga (idempotencia, backoff,
recuperación entre reintentos y fallos permanentes) y la bandeja de salida (escritura
transaccional, relay, backoff, agotamiento de intentos y reencolado). Corren sobre SQLite,
sin Pulsar:

```bash
DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests
# solo la bandeja de salida
DATABASE_URL="sqlite:///:memory:" python3 -m unittest tests.test_outbox -v
# solo unidad de trabajo y saga
DATABASE_URL="sqlite:///:memory:" python3 -m unittest tests.test_unidad_de_trabajo_y_saga -v
```

La prueba que sostiene el patrón es
`test_un_fallo_antes_de_confirmar_no_deja_ni_saldo_ni_evento`: si la transacción se
revierte, no queda ni el movimiento ni su anuncio. Y la que lo demuestra en operación es
`test_cuando_el_broker_vuelve_sale_lo_acumulado`.

`app/infraestructura/configuracion.py` carga ese `.env` al arrancar, resolviendo la ruta
desde el propio archivo y no desde el directorio de trabajo, así que no hacen falta
banderas ni exportar nada. Una variable ya presente en el entorno tiene prioridad sobre
el `.env`, de modo que en despliegue basta exportarla. Los `export` de los ejemplos
siguientes solo son necesarios si prefiere no usar el archivo.

### Opción A — PostgreSQL con Docker

Esta es la forma recomendada para levantar rápidamente la base exigida por la entrega.
El `docker-compose.yml` vive en la raíz del repositorio:

```bash
docker compose -f ../docker-compose.yml up -d postgres
export DATABASE_URL=postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

### Opción B — PostgreSQL instalado localmente

No se necesita Docker si ya existe una instancia local. Cree previamente la base y el
usuario, y sustituya los valores de conexión según su instalación:

```bash
export DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/wallet_db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

### Opción C — SQLite sin Docker ni servidor de base de datos

Para una demostración o desarrollo rápido puede utilizarse un archivo SQLite local:

```bash
mkdir -p app/data
export DATABASE_URL=sqlite+pysqlite:///./app/data/wallet.db
uvicorn app.infraestructura.adaptadores.entrada.api.main:app --reload
```

SQLite permite ejecutar todos los endpoints sin infraestructura adicional. Sin embargo,
la especificación académica establece PostgreSQL como tecnología de persistencia; por
eso las opciones A, B o D son las apropiadas para validar formalmente la entrega.

### Opción D — Todo en Docker, detrás de la entrada pública

Desde la raíz del repositorio levante todos los servicios y el gateway:

```bash
docker compose up -d --build --wait
```

WalletBC queda publicado en <http://localhost/wallet/> (por ejemplo
`http://localhost/wallet/billeteras`) y su documentación en <http://localhost/wallet/docs>.
El puerto 8000 sigue aceptando llamadas a la API desde la propia máquina, pero Swagger solo
carga a través del gateway, porque en Docker el servicio corre con `UVICORN_ROOT_PATH=/wallet`.
Consulte el [README raíz](../README.md#despliegue-con-docker-y-entrada-pública).

En las opciones A, B y C la documentación interactiva queda en <http://localhost:8000/docs>.
Las tablas se crean al iniciar el servicio. Para producción se recomienda sustituir esta inicialización por
migraciones versionadas.

## API REST

| Método | Ruta | Para qué |
|---|---|---|
| `POST` | `/billeteras` | Crear la billetera de un proveedor |
| `GET` | `/billeteras` | Listar billeteras con paginación y filtros |
| `GET` | `/billeteras/{id}` | Detalle administrativo de una billetera |
| `PATCH` | `/billeteras/{id}` | Cambiar el estado: `Activa` o `Suspendida` |
| `DELETE` | `/billeteras/{id}` | Eliminar una billetera sin saldo |
| `GET` | `/billeteras/{id}/saldo` | Saldo y estado actuales |
| `POST` | `/billeteras/{id}/acreditar` | Registrar un crédito |
| `POST` | `/billeteras/{id}/debitar` | Registrar un débito |
| `GET` | `/billeteras/{id}/movimientos` | Historial, con filtros de fecha y tipo |
| `GET` | `/billeteras/{id}/movimientos/{movimiento_id}` | Un movimiento puntual |
| `POST` | `/proveedores/{proveedor_id}/wallet/retiros` | Retiro solicitado por el proveedor |
| `POST` | `/eventos-externos/trabajo-liquidado` | Evento externo simulado |

`POST /proveedores/{proveedor_id}/wallet/retiros` identifica la billetera **por el
proveedor**, no por el id contable de la billetera, que es un detalle interno de WalletBC.
Es la ruta que consume el BFF y la que corresponde al comando de retiros del contrato de
arquitectura:

```bash
curl -X POST http://localhost:8000/proveedores/prov-hda-expert-01/wallet/retiros \
  -H 'Content-Type: application/json' \
  -d '{"monto":"50000.00","referencia_externa":"retiro-1"}'
```

El `motivo` por omisión es `RetiroAProveedor`. Responde `404` si el proveedor no tiene
billetera y `409` por fondos insuficientes.

Use UUID diferentes para el proveedor y los trabajos. Primero cree una billetera:

```bash
curl -X POST http://localhost:8000/billeteras \
  -H 'Content-Type: application/json' \
  -d '{"proveedor_id":"11111111-1111-4111-8111-111111111111","moneda":"COP"}'
```

Copie el campo `id` de la respuesta en `BILLETERA_ID`:

```bash
export BILLETERA_ID=<id-de-la-billetera>

curl http://localhost:8000/billeteras/$BILLETERA_ID/saldo

curl -X POST http://localhost:8000/billeteras/$BILLETERA_ID/acreditar \
  -H 'Content-Type: application/json' \
  -d '{"monto":"150000.00","motivo":"AjusteManual","referencia_externa":"ajuste-1"}'

curl -X POST http://localhost:8000/billeteras/$BILLETERA_ID/debitar \
  -H 'Content-Type: application/json' \
  -d '{"monto":"25000.00","motivo":"RetiroAProveedor"}'

curl "http://localhost:8000/billeteras/$BILLETERA_ID/movimientos?tipo=Credito"

curl -X POST http://localhost:8000/eventos-externos/trabajo-liquidado \
  -H 'Content-Type: application/json' \
  -d '{"trabajo_id":"22222222-2222-4222-8222-222222222222","proveedor_id":"11111111-1111-4111-8111-111111111111","monto":"80000.00","moneda":"COP"}'
```

Los valores permitidos son:

- `motivo`: `PagoDeTrabajo`, `RetiroAProveedor`, `AjusteManual` o `Reverso`.
- filtro `tipo`: `Credito` o `Debito`.
- filtros de fecha: `fecha_desde` y `fecha_hasta` en formato ISO 8601.

### Administración de las billeteras

El listado devuelve una página, no un arreglo suelto, para que el cliente sepa cuántos
registros quedan. Acepta `estado`, `proveedor_id`, `limite` (1 a 200, por omisión 50) y
`desplazamiento`:

```bash
curl "http://localhost:8000/billeteras?estado=Activa&limite=20&desplazamiento=0"
# {"items":[...],"total":37,"limite":20,"desplazamiento":0}

curl http://localhost:8000/billeteras/$BILLETERA_ID
# agrega fecha_creacion y total_movimientos al saldo
```

La única actualización admitida es el estado. El saldo no se edita: se mueve con
`acreditar` y `debitar` para que cada peso quede respaldado por un movimiento, y el
proveedor y la moneda son parte de la identidad contable de la billetera.

```bash
curl -X PATCH http://localhost:8000/billeteras/$BILLETERA_ID \
  -H 'Content-Type: application/json' \
  -d '{"estado":"Suspendida"}'
```

Una billetera suspendida rechaza los débitos y publica `DebitoRechazadoV1`. El cambio de
estado emite `EstadoBilleteraCambiadoV1` con el estado anterior; repetir el estado actual
responde `200` sin emitir evento, porque no hubo un hecho nuevo.

```bash
curl -X DELETE http://localhost:8000/billeteras/$BILLETERA_ID   # 204, o 409 si tiene saldo
```

El borrado es físico y arrastra los movimientos en cascada, pero solo procede con saldo
cero: un saldo positivo es dinero adeudado al proveedor, y eliminarlo lo haría desaparecer
sin contrapartida contable. Emite `BilleteraEliminadaV1` para que los demás bounded
contexts dejen de considerar esa billetera.

La API responde `201` al crear, `200` en operaciones exitosas, `204` al eliminar, `400`
ante datos o reglas inválidas, `404` si no existe la billetera o el movimiento, y `409`
ante fondos insuficientes, billetera duplicada o un borrado con saldo pendiente.
