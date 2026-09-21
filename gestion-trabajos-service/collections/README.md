# Colección Postman — GestionDeTrabajosBC

| Archivo | Qué es |
|---|---|
| `GestionTrabajosBC.postman_collection.json` | Flujo completo de un trabajo de Marketplace y casos de error del agregado |
| `GestionTrabajosBC.local.postman_environment.json` | Environment con `base_url` apuntando a `127.0.0.1:8001` |

Los escenarios de calidad con partners B2B2C (Interoperabilidad #9 y Modificabilidad #3) están
en la colección de [`operaciones-service/collections/`](../../operaciones-service/collections/README.md).

## Uso

1. Levante el servicio, desde la raíz del repositorio:

   ```bash
   docker compose up -d --build --wait gestion-trabajos
   ```

2. En Postman, **Import** → los dos archivos de esta carpeta, y seleccione el environment
   *GestionDeTrabajosBC — local*.
3. Ejecute la colección completa con el **Collection Runner**, en orden.

## Cómo está organizada

**01 Flujo Marketplace**: un trabajo con plomería → pintura.

| Paso | Qué demuestra |
|---|---|
| Crear trabajo | Plomería queda `Pendiente` y pintura `Bloqueado` |
| Asignar, iniciar y completar plomería | Pintura se desbloquea sola |
| Re-diagnóstico | Aparece electricidad y pintura vuelve a congelarse |
| Completar electricidad y pintura | Cada bloqueo se levanta cuando terminan todas sus dependencias |
| Cerrar | `Cerrado`, costo total 395.000 y `TrabajoCerradoV1` con liquidaciones |

**02 Casos de error**:

- trabajo inexistente (404);
- iniciar un sub-trabajo bloqueado (409);
- cerrar con sub-trabajos pendientes (409);
- completar sin evidencia (400);
- flujo con dependencias en ciclo (400, y se publica `CreacionDeTrabajoRechazadaV1`);
- categoría inexistente (400).

## Qué mirar en los logs

```
trabajos.domain_events      | domain_event=TrabajoCreado event_id=...
trabajos.integration_events | integration_event=TrabajoCreadoV2 {"event_type": "TrabajoCreado", "event_version": 2, ...}
```

Cada creación publica `TrabajoCreadoV1`, marcado `"deprecado": true`, y `TrabajoCreadoV2`: las
dos versiones del contrato conviven mientras los consumidores migran.
