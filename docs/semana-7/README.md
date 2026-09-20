# Entrega Semana 7 — Transacciones Distribuidas (Sagas), Saga Log, BFF y Experimentación
## Proyecto: Hogar de los Alpes

Este directorio contiene la documentación técnica y evidencias correspondientes a los entregables de la **Semana 7** del curso Diseño y Arquitectura de Aplicaciones No Monolíticas (DANM).

---

## 📑 Documentos del Entregable

1. **[Patrón de Sagas y Saga Log](patron-sagas-y-saga-log.md)**
   - Justificación del modelo de orquestación frente a coreografía.
   - Especificación de la máquina de estados y microservicios participantes.
   - Detalle del flujo exitoso (*Happy Path*) y del flujo compensatorio ante fallos.
   - Estructura del almacén persistente de *Saga Log* y consultas SQL de auditoría.

2. **[Backend For Frontend (BFF)](backend-for-frontend-bff.md)**
   - Propósito, arquitectura y responsabilidades del BFF como fachada síncrona.
   - Especificación de endpoints de agregación y activación de transacciones de larga duración.
   - Estrategia de desacoplamiento de clientes frente al broker de eventos interno.

3. **[Informe Técnico de Resultados de Experimentación](informe-experimentacion.md)**
   - Resumen ejecutivo y definición formal de hipótesis por escenario de calidad.
   - Metodología, herramientas y ambiente de ejecución de pruebas.
   - Resultados cuantitativos (latencias, throughput, tiempos de recuperación) y cualitativos.
   - Validación final de cumplimiento de hipótesis.

4. **[Refinamiento de Arquitectura TO-BE y Vistas Dinámicas](arquitectura-to-be-refinada.md)**
   - Mapa de contextos acotados TO-BE actualizado (ContextMapper DSL y Mermaid).
   - Diagramas de secuencia del ciclo de vida de la Saga (Happy Path y Compensación).
   - Topología física y lógica de despliegue consolidada.
