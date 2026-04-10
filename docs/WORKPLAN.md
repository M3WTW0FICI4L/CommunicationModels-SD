# 🧠 🗺️ Plan de desarrollo recomendado

## 🔹 Fase 0 — Entender bien el problema (MUY IMPORTANTE)

Antes de escribir código:

1. Identifica los **dos ejes principales**:

   * Tipo de ticket:

     * Unnumbered → rendimiento
     * Numbered → consistencia
   * Arquitectura:

     * Directa
     * Indirecta (con RabbitMQ)

2. Define el **invariante crítico**:

   * ❌ Nunca vender más de 20,000 tickets
   * ❌ Nunca vender el mismo asiento dos veces

👉 Esto es lo más importante del proyecto.

---

# 🔹 Fase 1 — Diseño base (ANTES de programar)

## 1.1 Elegir stack tecnológico

Recomendación práctica:

* Backend:

  * Python (FastAPI o Flask)
* Base de datos / estado:

  * Redis (rápido y simple)
* Broker:

  * RabbitMQ
* Load balancer:

  * NGINX
* Infraestructura:

  * AWS

---

## 1.2 Diseñar modelo de datos

### Unnumbered

* contador global:

```
tickets_sold = 0
```

### Numbered

* estructura:

```
seat_id → available / sold
```

En Redis:

* `INCR` → unnumbered
* `SETNX` → numbered (clave)

---

## 1.3 Diseñar arquitectura (dibujar esto)

### Directa

```
Client → Load Balancer → Server → Redis
```

### Indirecta

```
Client → RabbitMQ → Worker(s) → Redis
```

---

# 🔹 Fase 2 — Implementar versión SIMPLE (baseline)

👉 Empieza por lo más fácil: **UNNUMBERED + DIRECT**

## 2.1 API básica (Direct)

Endpoint:

```
POST /buy
```

Lógica:

```
if tickets_sold < 20000:
    increment
    success
else:
    fail
```

⚠️ Usa operación atómica en Redis:

* `INCR` + check

---

## 2.2 Cliente de benchmark

* Leer archivo línea por línea
* Enviar requests concurrentes (threads o async)

---

## 2.3 Métricas básicas

* tiempo total
* ops/sec
* éxito / fallo

---

# 🔹 Fase 3 — Añadir concurrencia real

## 3.1 Simular carga

* 50, 100, 500 clientes concurrentes
* medir throughput

---

## 3.2 Detectar problemas

* overselling ❌
* race conditions ❌

Si ocurre → arreglar YA antes de seguir

---

# 🔹 Fase 4 — Numbered tickets (consistencia)

Aquí empieza lo difícil.

## 4.1 Implementación segura

En Redis:

```
SETNX seat_123 "sold"
```

Si falla → asiento ya vendido

---

## 4.2 Manejo de contención

Muchos clientes intentarán:

```
seat 1, 2, 3...
```

👉 Aquí verás:

* colisiones
* latencia
* retries

---

# 🔹 Fase 5 — Load balancing (Direct)

## 5.1 Añadir múltiples servidores

* 2–3 instancias backend

## 5.2 Configurar NGINX

* round-robin
* un solo entry point (requisito)

---

## 5.3 Medir escalabilidad

Gráfica:

```
workers vs throughput
```

---

# 🔹 Fase 6 — Arquitectura indirecta (RabbitMQ)

## 6.1 Flujo

```
Client → Queue → Worker → Redis
```

---

## 6.2 Producer (cliente)

* envía mensaje a cola:

```
BUY client_id seat_id request_id
```

---

## 6.3 Worker

* consume mensajes
* procesa compra
* guarda resultado

---

## 6.4 Respuesta

Opciones:

* simple: log + archivo
* avanzado: cola de respuesta

---

# 🔹 Fase 7 — Escalado dinámico

## 7.1 Añadir workers en caliente

* lanzar más workers mientras corre el sistema

👉 Debe:

* aumentar throughput
* no romper consistencia

---

## 7.2 Test

* 1 worker → baseline
* 2, 4, 8 workers

---

# 🔹 Fase 8 — Escenario de alta contención

Modificar benchmark:

* 80% → 5% de asientos

---

## 8.1 Qué observar

* colas creciendo
* latencia
* workers bloqueados

---

## 8.2 Comparar:

| Arquitectura | Resultado esperado      |
| ------------ | ----------------------- |
| Direct       | peor bajo contención    |
| Indirect     | mejor absorbiendo picos |

---

# 🔹 Fase 9 — Experimentos y métricas

## 9.1 Medir SIEMPRE

* tiempo total
* throughput
* éxito/fallo

---

## 9.2 Gráficas obligatorias

* throughput vs workers
* direct vs indirect
* numbered vs unnumbered

---

# 🔹 Fase 10 — Deployment en AWS

## 10.1 Distribución típica

* VM1 → NGINX + API
* VM2 → API
* VM3 → Redis
* VM4 → RabbitMQ + workers

---

## 10.2 Validación

⚠️ Importante:

* debe correr en AWS (no solo local)

---

# 🔹 Fase 11 — (Opcional) Fallos

Simula:

* matar worker
* reiniciar Redis

Verifica:

* no overselling
* no duplicados

---

# 🔹 Fase 12 — Reporte

Estructura:

1. Arquitectura
2. Decisiones (por qué Redis, RabbitMQ, etc.)
3. Resultados
4. Comparación:

   * Direct vs Indirect
   * Throughput vs Consistencia
5. Conclusiones reales

---

# ⚠️ Errores típicos (evítalos)

* ❌ No usar operaciones atómicas
* ❌ Probar solo en local
* ❌ Ignorar contención
* ❌ No medir correctamente
* ❌ Mezclar lógica entre arquitecturas

---

# 🧭 Orden recomendado (muy importante)

1. ✅ Unnumbered + Direct
2. ✅ Numbered + Direct
3. ✅ Load balancing
4. ✅ RabbitMQ (Indirect)
5. ✅ Escalado dinámico
6. ✅ Alta contención
7. ✅ Experimentos + gráficas
8. ✅ AWS deployment

---

# 🚀 Consejo final

Este proyecto **no es de código, es de sistemas distribuidos**:

👉 Lo que te van a evaluar es:

* decisiones
* tradeoffs
* análisis

---