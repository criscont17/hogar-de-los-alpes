# Colección Postman — GestionDeTrabajosBC

| Archivo | Qué es |
|---|---|
| `GestionTrabajosBC.postman_collection.json` | Colección con el flujo completo, la capa anti-corrupción, la resiliencia y los casos de error |
| `GestionTrabajosBC.local.postman_environment.json` | Environment con `base_url` apuntando a `localhost:8001` |

## Uso

1. Levante el servicio en el puerto 8001 de una de estas dos formas:

   - **En Docker** (desde la raíz del repositorio):
     ```bash
     docker compose up -d --build --wait gestion-trabajos
     ```
   - **Local, sin Docker** (desde `gestion-trabajos-service`, en PowerShell):
     ```powershell
     New-Item -ItemType Directory -Force app\data
     $env:DATABASE_URL="sqlite+pysqlite:///./app/data/trabajos.db"
     $env:MESSAGE_BROKER="logging"
     .venv\Scripts\python.exe -m uvicorn app.infraestructura.adaptadores.entrada.api.main:app --port 8001
     ```

2. En Postman, **Import** → arrastre los dos archivos de esta carpeta.
3. Seleccione el environment *GestionDeTrabajosBC — local*.
4. Ejecute las carpetas **01 a 04** con el **Collection Runner**, en orden: cada una
   reutiliza variables de las anteriores. La carpeta 05 se ejecuta aparte (ver abajo).

Las referencias (`numero_siniestro`, `id_orden`, `order_id`) y el proveedor se generan en
cada corrida, así que la colección se puede ejecutar varias veces sin limpiar la base.

## Cómo está organizada

**01 Flujo Marketplace**: un trabajo con plomería → pintura.

| Paso | Qué demuestra |
|---|---|
| Crear trabajo | Plomería queda `Pendiente` y pintura `Bloqueado` |
| Asignar, iniciar y completar plomería | Pintura se desbloquea sola |
| Re-diagnóstico | Aparece electricidad y pintura vuelve a congelarse |
| Completar electricidad y pintura | Cada bloqueo se levanta cuando terminan todas sus dependencias |
| Cerrar | `Cerrado`, costo total 395.000 y `TrabajoCerradoV1` con liquidaciones |

**02 Partners B2B2C (ACL)**: el mismo core recibe tres formatos distintos.

| Partner | Formato | Qué verificar |
|---|---|---|
| Seguros de los Alpes | JSON propio | Responde en su formato, reintentar devuelve 200 con el mismo trabajo, la vista canónica tiene SLA 24 h |
| Banco Andino | SOAP | Responde `text/xml` con `REGISTRADA`; las etapas quedan como dependencias |
| Muebles del Hogar | Webhook | Cinco pasos de instalación en estado `scheduled` |

**03 Resiliencia (circuit breaker)**: es la medida del escenario de interoperabilidad.

1. Se simula la caída del core de Seguros.
2. Asignar un proveedor al siniestro responde en menos de 1 s: el flujo interno no espera
   al partner.
3. La salud de Seguros muestra la novedad pendiente y la degradación.
4. Se cancela la orden del Banco: su salud muestra circuito `Cerrado` y la cancelación
   entregada. La caída de un partner no afectó al otro.
5. Se restaura Seguros y, sin intervención, lo pendiente se entrega y el circuito se cierra.
   El último request espera 12 s, lo que tarda en vencer `PARTNER_CB_RECUPERACION_SEGUNDOS`.

**04 Casos de error**: sub-trabajo bloqueado (409), proveedor fuera de la red homologada
(409), sobrecosto sobre el tope de la póliza (409), cierre incompleto (409), completar sin
evidencia (400), flujo en ciclo (400), partner no integrado (404) y solicitud intraducible
(400).

**05 Onboarding de un partner nuevo (Modificabilidad)**: la medida del escenario es que
integrar un partner no modifique el dominio. Se demuestra con el mismo request antes y
después de agregar un adaptador. Por eso se ejecuta en dos momentos:

1. Con el servicio tal como está, corra **05.1**. `cooperativa-sur` responde 404 y no
   aparece en `/partners`.
2. Integre el partner, sin tocar dominio ni aplicación:
   - copie `ejemplos/onboarding/cooperativa_sur.py` a
     `app/infraestructura/adaptadores/acl_partners/`;
   - en `registro.py` agregue `from .cooperativa_sur import CooperativaSurAdapter` y la
     clase al final de `ADAPTADORES_REGISTRADOS`;
   - reinicie el servicio. En Docker, reconstruya la imagen:
     `docker compose up -d --build gestion-trabajos`.
3. Corra **05.2**. La orden en texto plano responde 201 en el formato de la cooperativa,
   el reintento no duplica, y la vista canónica muestra el flujo
   `Plomeria → Electricidad + Pintura` en pesos argentinos.
4. Compruebe la medida con `git diff --stat -- app/dominio app/aplicacion`, que debe
   salir vacío.

Para repetir la demostración, deshaga los dos cambios del paso 2 y reinicie.

## Qué mirar en los logs

```
trabajos.domain_events      | domain_event=TrabajoCreado event_id=...
trabajos.integration_events | integration_event=TrabajoCreadoV2 {"event_type": "TrabajoCreado", "event_version": 2, ...}
trabajos.partners           | partner_core=seguros-alpes recibio operacion=PROVEEDOR_ASIGNADO ...
trabajos.partners           | sincronizacion_degradada partner=seguros-alpes operacion=PROVEEDOR_ASIGNADO pendientes=1 circuito=Cerrado ...
```

- Cada creación publica `TrabajoCreadoV1` marcado `"deprecado": true` y `TrabajoCreadoV2`:
  las dos versiones del contrato conviven mientras los consumidores migran.
- Durante la carpeta 03 aparecen líneas `sincronizacion_degradada` solo para
  `seguros-alpes`, nunca para `banco-andino`.
