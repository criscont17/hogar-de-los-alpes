# Entrega Semana 7 — Transacciones Distribuidas (Sagas), Saga Log, BFF y Experimentación
## Proyecto: Hogar de los Alpes

Este directorio contiene la documentación técnica y evidencias correspondientes a los entregables de la **Semana 7** del curso Diseño y Arquitectura de Aplicaciones No Monolíticas (DANM).

---

## 📑 Documentos del Entregable

1. **[Patrón de Sagas y Saga Log](patron-sagas-y-saga-log.md)**
   - Justificación del modelo de orquestación frente a coreografía.
   - Especificación de la máquina de estados y microservicios participantes (`GestionDeTrabajosBC`, `PagosBC`, `OperacionesBC`).
   - Detalle del flujo exitoso (*Happy Path*) y del flujo compensatorio ante fallos (orden inverso).
   - Estructura del almacén persistente de *Saga Log* (`saga_instancias`, `saga_pasos`) y consultas SQL de auditoría.
   - Guía de reproducción de pruebas en memoria y con Docker/Pulsar.

2. **[Backend For Frontend (BFF)](backend-for-frontend-bff.md)**
   - Propósito, arquitectura y responsabilidades del BFF como fachada síncrona.
   - Especificación de endpoints de agregación y activación de transacciones de larga duración.
   - Estrategia de desacoplamiento de clientes frente al broker de eventos interno.

3. **[Informe Técnico de Resultados de Experimentación](informe-experimentacion.md)**
   - Resumen ejecutivo y definición formal de hipótesis por escenario de calidad.
   - Metodología, herramientas y ambiente de ejecución de pruebas.
   - Resultados cuantitativos (latencias, throughput, tiempos de recuperación) y cualitativos.
   - Validación final de cumplimiento de hipótesis.

4. **[Experimentos de los Escenarios de Calidad de la Saga](experimentos-escenarios-saga.md)**
   - Protocolo de ejecución de los escenarios de elasticidad, disponibilidad y consistencia.
   - Hipótesis, métricas y umbrales de cada escenario, con los comandos automatizados.
   - Interpretación de resultados, amenazas a la validez y plantillas de tablas para el informe.

5. **[Refinamiento de Arquitectura TO-BE y Vistas Dinámicas](arquitectura-to-be-refinada.md)**
   - Mapa de contextos acotados TO-BE actualizado: [`hda-context-map-to-be-refinado.cml`](hda-context-map-to-be-refinado.cml) (ContextMapper DSL) y su diagrama Mermaid.
   - Diagramas de secuencia del ciclo de vida de la Saga (Happy Path y Compensación).
   - Topología física y lógica de despliegue consolidada.

---

## 🚀 Verificación Rápida de la Entrega

### Pruebas de la Saga y Saga Log (en memoria):
```bash
python3 gestion-trabajos-service/scripts/test_unitario_saga.py
```

### Pruebas de la Unidad de Trabajo (UoW en Pagos):
```bash
cd pagos-service
DATABASE_URL="sqlite:///:memory:" python3 -m unittest discover -s tests
```

### Pruebas de Integración con Docker y Apache Pulsar:
```bash
# Levantar el stack completo
docker compose up -d

# Probar camino exitoso
python3 -m gestion-trabajos-service.scripts.probar_saga_orquestada --modo exito

# Probar compensación por rechazo en operaciones
python3 -m gestion-trabajos-service.scripts.probar_saga_orquestada --modo compensar-operaciones

# Probar compensación por rechazo en pago
python3 -m gestion-trabajos-service.scripts.probar_saga_orquestada --modo compensar-pago
```
