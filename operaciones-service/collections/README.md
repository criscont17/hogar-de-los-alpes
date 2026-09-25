# Colección Postman — Escenarios de calidad

| Archivo | Qué es |
|---|---|
| `EscenariosDeCalidad.postman_collection.json` | Escenarios de Interoperabilidad (#9) y Modificabilidad (#3) sobre OperacionesBC y GestionDeTrabajosBC |
| `EscenariosDeCalidad.local.postman_environment.json` | Environment con `base_operaciones` (8002) y `base_trabajos` (8001) |
| `PresentacionInteroperabilidad.aws.postman_collection.json` | Solo el escenario 9 (carpetas 01 a 04) contra la VM de AWS, a través de la entrada pública; no necesita environment |

## Preparación

1. Desde la raíz del repositorio levante los dos servicios, con sus bases y Pulsar:

   ```bash
   docker compose up -d --build --wait gestion-trabajos operaciones
   ```

2. En Postman, **Import** → los dos archivos de esta carpeta.
3. Seleccione el environment **Escenarios de calidad — local**.
4. Deje los logs a la vista: `docker compose logs -f operaciones gestion-trabajos`.

Cada request indica a qué servicio va: `{{base_operaciones}}` es OperacionesBC y
`{{base_trabajos}}` es GestionDeTrabajosBC. Varios requests esperan 3 segundos antes de
enviarse: el trabajo se crea de forma asíncrona por Pulsar.

## Escenario 9 — Interoperabilidad

> **Estímulo:** los partners B2B2C envían solicitudes en su propio formato y con sus reglas.
> **Medida:** el 100 % se traduce al modelo canónico sin contaminar el core, y ante la falla de
> un partner el sistema se recupera en segundos sin degradar a los demás.

Ejecute las carpetas **01 a 04** juntas y en orden con el **Collection Runner**. Tardan cerca de
40 segundos.

**01 Partners y acuerdos comerciales**

| Request | Resultado esperado |
|---|---|
| Partners con acuerdo y adaptador | `seguros-alpes`, `banco-andino` y `muebles-hogar`, todos con `tiene_adaptador: true` |
| Acuerdo comercial de Seguros de los Alpes | Condición `TOPE` PLUS = 4.000.000 y red de 2 proveedores: las reglas son datos, no código |

**02 Interoperabilidad: traducción de formatos**

| Request | Resultado esperado | Qué demuestra |
|---|---|---|
| Seguros (REST propio) → crear siniestro | `202`, `estado: RECIBIDO`, `topePoliza: 4000000`, `slaHoras: 24` | Traducción del formato y condiciones resueltas por el acuerdo |
| Seguros → reintento idempotente | `200` | Un reintento no vuelve a solicitar el trabajo |
| Seguros → consultar estado con su número | `idTrabajoHdA` con valor | GestionDeTrabajosBC creó el trabajo vía Pulsar |
| Vista canónica en GestionDeTrabajosBC | `canal: Partner`, `monto_maximo: 4000000`, `sla_horas: 24`, pintura `Bloqueado` | El core solo ve el modelo canónico |
| Banco Andino (SOAP) → crear orden | `202`, `text/xml`, `RECIBIDA` | Otro formato entra por el mismo caso de uso |
| Banco → consultar estado (SOAP) | `REGISTRADA` y 4 actividades | Las etapas SOAP quedaron como dependencias |
| Muebles del Hogar (webhook) → solicitar instalación | `202`, `status: received` | Tercer formato |
| Muebles → consultar instalación | `status: scheduled`, 5 pasos | Instalación orquestada por el core |

**03 Interoperabilidad: falla de un partner**

| Request | Resultado esperado | Qué demuestra |
|---|---|---|
| Simular caída del core de Seguros | `core_disponible: false` | Falla del partner |
| Asignar proveedor en GestionDeTrabajosBC con el partner caído | `200` en menos de 1 s | El core no conoce ni espera al partner |
| Salud de Seguros: sincronización degradada | `pendientes ≥ 1`, `degradaciones ≥ 1` | La novedad queda pendiente en OperacionesBC |
| Cancelar la orden del Banco en GestionDeTrabajosBC | `200` | Otro partner sigue operando |
| Salud del Banco: no se degradó | circuito `Cerrado`, `pendientes: 0`, `sincronizados ≥ 1` | La falla de uno no degrada a los demás |
| Restaurar el core de Seguros | `200` | El partner vuelve |
| Salud de Seguros: recuperación automática | Tras 12 s: `pendientes: 0`, circuito `Cerrado` | Recuperación en segundos, sin intervención |

**04 Reglas del acuerdo y rechazos**

| Request | Resultado esperado |
|---|---|
| Plan de póliza no pactado → 400 | "El acuerdo no pacta un tope para 'DORADO'"; no se envía nada al core |
| Tope de la orden mayor al pactado → 409 | La orden autoriza 60.000 MXN y el acuerdo pacta 50.000 |
| Partner no registrado → 404 | — |
| GestionDeTrabajosBC aplica la red del acuerdo → 409 | Proveedor fuera de la red homologada |
| GestionDeTrabajosBC aplica el tope del acuerdo → 409 | Sobrecosto sobre el tope |
| Solicitud con flujo inválido → 202 | OperacionesBC la acepta: el formato es válido |
| El rechazo asíncrono llega al partner | `estado: RECHAZADO` con el motivo de GestionDeTrabajosBC |

En los logs, durante la carpeta 03, aparece `sincronizacion_degradada partner=seguros-alpes`
y ninguna degradación para `banco-andino`.

## Escenario 3 — Modificabilidad

> **Estímulo:** se incorpora un partner nuevo con sus reglas y su formato. **Medida:** 0 % de
> componentes del dominio de GestionDeTrabajosBC modificados.

La carpeta **05** se ejecuta por partes, no junto con las demás.

1. **05.1 Antes del onboarding:** `POST /partners/cooperativa-sur/trabajos` responde `404` ("no
   está registrado").
2. **05.2 Onboarding contractual, sin código:**
   - `PUT /partners/cooperativa-sur` registra su acuerdo (tope 800.000 ARS, SLA URGENTE 24 h).
   - Enviar una orden todavía responde `404` "no tiene un adaptador de integración".
3. **Integración técnica, solo en OperacionesBC.** Desde `operaciones-service`:

   ```powershell
   Copy-Item ejemplos\onboarding\cooperativa_sur.py app\infraestructura\adaptadores\acl_partners\
   ```

   En `app/infraestructura/adaptadores/acl_partners/registro.py` agregue las dos líneas
   marcadas:

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

   Anote el tiempo de actividad de GestionDeTrabajosBC con `docker compose ps gestion-trabajos`
   y reconstruya **solo** OperacionesBC desde la raíz del repositorio:

   ```bash
   docker compose up -d --build --wait operaciones
   ```

4. **05.3 Después de agregar el adaptador:**

   | Request | Resultado esperado |
   |---|---|
   | Partners (con la cooperativa integrada) | `tiene_adaptador: true` |
   | Cooperativa Sur crea una orden en texto plano → 202 | `...\|RECIBIDA\|...`: el mismo request que antes daba 404 |
   | Reintento de la misma orden → 200 | Idempotencia heredada del caso de uso genérico |
   | La cooperativa consulta su orden | `...\|REGISTRADA\|0/3\|...` con el id del trabajo |
   | Vista canónica en GestionDeTrabajosBC | `Partner`, `AR`, `ARS`, tope 800.000, SLA 24 h; plomería `Pendiente`, electricidad y pintura `Bloqueado` |

5. **Verificar la medida:**
   - `git status gestion-trabajos-service` no muestra cambios;
   - `docker compose ps gestion-trabajos` muestra el mismo tiempo de actividad del paso 3: el
     core no se modificó ni se reinició.

Para repetir la demostración, borre `acl_partners/cooperativa_sur.py`, quite las dos líneas de
`registro.py` y reconstruya OperacionesBC. El acuerdo registrado puede quedarse: 05.2 lo
renegocia sin error.
