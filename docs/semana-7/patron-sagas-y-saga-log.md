# Especificación del Patrón de Sagas y Saga Log
## Entrega Semana 7 — Hogar de los Alpes

---

## 1. Justificación del Patrón Transaccional
### 1.1 Modelo Seleccionado: Orquestación vs. Coreografía
<!-- Justificar técnicamente la elección de Sagas por Orquestación (visibilidad global, centralización de compensaciones, prevención de ciclos y facilidad para auditoría). -->

### 1.2 Microservicios Participantes en la Transacción
<!-- Listar los al menos 3 microservicios involucrados y el rol específico de cada uno en la transacción distribuida. -->

---

## 2. Especificación de la Máquina de Estados de la Saga
### 2.1 Estados Globales y Transiciones
<!-- Detallar los estados de la saga (e.g., INICIADA, EN_PROCESO, COMPLETADA, COMPENSANDO, COMPENSADA, FALLIDA). -->

### 2.2 Tópicos y Canales de Mensajería
<!-- Listar los tópicos de comandos y eventos utilizados sobre Apache Pulsar. -->

---

## 3. Flujos Transaccionales
### 3.1 Flujo Exitoso (Happy Path)
<!-- Descripción paso a paso de la ejecución secuencial completa sin errores. -->

### 3.2 Flujo Compensatorio ante Fallos
<!-- Descripción del escenario de fallo forzado o de negocio y la secuencia de compensación en orden inverso. -->

---

## 4. Persistencia y Auditoría con Saga Log
### 4.1 Modelo de Datos Relacional
<!-- Documentar la estructura de tablas (ej. saga_instancias y saga_pasos) y campos obligatorios. -->

### 4.2 Consultas SQL de Monitoreo y Verificación
<!-- Incluir las sentencias SQL para auditar el estado y progreso cronológico de una transacción. -->
```sql
-- Consultas de verificación de Saga Log
```

---

## 5. Guía de Reproducción de Pruebas
<!-- Instrucciones breves para ejecutar o reproducir ambos caminos (éxito y compensación). -->
