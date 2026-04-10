# CommunicationModels-SD

Sistema escalable de adquisición de entradas para comparar middleware de comunicación directa vs indirecta bajo alta carga y contención.

[![codecov](https://codecov.io/gh/M3WTW0FICI4L/CommunicationModels-SD/graph/badge.svg?token=QV602QYGAO)](https://codecov.io/gh/M3WTW0FICI4L/CommunicationModels-SD)

## Qué implementa este proyecto

- Dos modelos de entradas:
	- `unnumbered` (máximo 20.000 ventas)
	- `numbered` (asiento `1..20000`, sin doble venta)
- Dos arquitecturas de comunicación:
	- Directa: API REST + balanceador NGINX + Redis
	- Indirecta: RabbitMQ + workers + Redis
- Núcleo de corrección compartido en `src/backend`

## Estructura del repositorio

	- `src/backend/`: consistencia y lógica de tickets (compartido por ambas arquitecturas)
	- `src/direct/`: servidor API + cliente + componentes de balanceo
	- `src/indirect/`: configuración de cola + productor + pool de workers
	- `src/experiments/`: runners de benchmark y utilidades de métricas
	- `results/direct/numbered/`
	- `results/direct/numbered/contention/`
	- `results/direct/unnumbered/`
	- `results/indirect/numbered/`
	- `results/indirect/numbered/contention/`
	- `results/indirect/unnumbered/`
	- `results/tests/`
	- `results/plots/`

- `scripts/`: setup, orquestación de benchmarks, generación de plots y tests
- `tests/`: pruebas de tipo unit/integration para módulos core
	- Verifica/instala Docker + Compose, corrige permisos y comprueba acceso al daemon.

- `scripts/setup_docker.sh`

- `scripts/run_all_benchmarks.sh`
	- Punto de entrada principal de benchmark.
	- Ejecuta la matriz para ambas arquitecturas y ambos tipos de ticket con concurrencias:
		`1 2 4 8 16 32 50`.
	- También ejecuta una **matriz de alta contención** (solo numbered) para ambas arquitecturas.
	- Guarda resultados JSON en la estructura tipada bajo `results/`.
	- Argumento opcional 4º `SERVER_HOST`: si se establece a una dirección no-localhost, omite el ciclo de vida de Docker local y apunta a un servidor remoto.

- `scripts/run_contention_benchmark.sh`
	- Ejecución única de alta contención para el modelo `numbered`.
	- Soporta ambas arquitecturas:
		- `./scripts/run_contention_benchmark.sh direct <concurrency> <api_url>`
		- `./scripts/run_contention_benchmark.sh indirect <concurrency>`
	- Guarda JSON en:
		- `results/direct/numbered/contention/`
		- `results/indirect/numbered/contention/`

- `scripts/run_direct_benchmark.sh`
	- Ejecución benchmark directa para un tipo de ticket y una concurrencia.

- `scripts/run_indirect_benchmark.sh`
	- Ejecución benchmark indirecta para un tipo de ticket y una concurrencia.

- `scripts/run_tests.sh`
	- Ejecuta la suite de tests con cobertura.
	- Guarda artefactos en `results/tests/`:
		- log de pytest
		- JUnit XML
		- carpeta de cobertura HTML con timestamp

- `scripts/plot_results.py`
	- Carga JSON de benchmark de forma recursiva desde `results/direct/**` y `results/indirect/**`.
	- Genera plots estándar en `results/plots/`.
	- Genera plots de comparación de contención cuando existe data de contención:
		- `direct_vs_indirect_contention_numbered.png`
		- `latency_p95_comparison_contention_numbered.png`

- `scripts/generate_contention_benchmark.py`
	- Genera una carga `numbered` de alta contención (80% del tráfico contra 5% de asientos).
	- Úsalo para los experimentos adicionales de contención solicitados en los requisitos.

## Dónde escribe `generate_contention_benchmark`

Por defecto escribe en:

- `benchmarks/benchmark_numbered_contention.txt`

Puedes cambiarlo con `--output`:

```bash
python3 scripts/generate_contention_benchmark.py \
	--output benchmarks/my_custom_contention.txt \
	--total 60000
```

El formato generado es compatible con el parser de benchmark `numbered`:

- `BUY <client_id> <seat_id> <request_id>`

## Cómo ejecutar tests

Recomendado (guarda todos los artefactos en `results/tests/`):

```bash
./scripts/run_tests.sh
```

Artefactos generados:

- `results/tests/pytest_<timestamp>.log`
- `results/tests/junit_<timestamp>.xml`
- `results/tests/htmlcov_<timestamp>/index.html`

Comandos opcionales directos de pytest:

```bash
pytest -v
pytest tests/test_models.py -v
pytest tests/test_ticket_manager.py::TestTicketManagerInitialization::test_ticket_manager_initialization -v
```

## Cómo ejecutar benchmarks

### A) Matriz completa (recomendado)

Ejecuta direct e indirect para ambos tipos de ticket con concurrencias:

- `1 2 4 8 16 32 50`

Comando:

```bash
./scripts/run_all_benchmarks.sh
```

Si Docker ya está configurado y quieres omitir setup:

```bash
./scripts/run_all_benchmarks.sh true
```

Para ejecutar contra un servidor remoto (ver [Ejecución en dos máquinas](#ejecución-en-dos-máquinas)):

```bash
./scripts/run_all_benchmarks.sh true false false <IP_SERVIDOR>
```

### B) Ejecuciones individuales

Ejecución directa individual:

```bash
./scripts/run_direct_benchmark.sh unnumbered 50 http://localhost:80
./scripts/run_direct_benchmark.sh numbered 50 http://localhost:80
```

Ejecución indirecta individual:

```bash
./scripts/run_indirect_benchmark.sh unnumbered 50
./scripts/run_indirect_benchmark.sh numbered 50
```

### C) Escenario de alta contención

Genera carga de contención (80/5):

```bash
python3 scripts/generate_contention_benchmark.py \
	--output benchmarks/benchmark_numbered_contention.txt \
	--total 60000
```

Ejecuta un benchmark de alta contención con el script dedicado:

```bash
./scripts/run_contention_benchmark.sh direct 50 http://localhost:80
./scripts/run_contention_benchmark.sh indirect 50
```

O ejecuta la matriz completa (incluyendo contención) con:

```bash
./scripts/run_all_benchmarks.sh
```

Si prefieres invocar el módulo de benchmark manualmente (ejemplo direct):

```bash
python3 -m src.main \
	--mode benchmark-direct \
	--ticket-type numbered \
	--workload benchmarks/benchmark_numbered_contention.txt \
	--concurrent-clients 50 \
	--api-url http://localhost:80 \
	--output results/direct/numbered/contention/c50_$(date +%Y%m%d_%H%M%S).json
```

## Ejecución en dos máquinas

Una máquina actúa como **servidor** (ejecuta Docker + contenedores) y la otra como **cliente** (ejecuta benchmarks, tests y plots). Ambas deben estar accesibles en la misma red.

Puertos que deben estar abiertos en el servidor:

| Puerto | Servicio           | Arquitectura |
|--------|--------------------|--------------|
| 80     | NGINX (REST API)   | Directa      |
| 5672   | RabbitMQ AMQP      | Indirecta    |
| 15672  | RabbitMQ UI (opt.) | Indirecta    |

### Máquina servidor: arrancar la arquitectura

```bash
# Directa
docker compose -f docker/docker-compose.direct.yml up -d --build

# Indirecta
docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4
```

### Máquina cliente: ejecutar benchmarks

**Opción A — script orquestrador (4º argumento = IP del servidor):**

```bash
# Solo benchmarks directos
./scripts/run_all_benchmarks.sh true false true <IP_SERVIDOR>

# Solo benchmarks indirectos
./scripts/run_all_benchmarks.sh true true false <IP_SERVIDOR>

# Ambos (el servidor debe tener los dos stacks corriendo simultáneamente)
./scripts/run_all_benchmarks.sh true false false <IP_SERVIDOR>
```

**Opción B — scripts individuales:**

```bash
# Directa
./scripts/run_direct_benchmark.sh unnumbered 50 http://<IP_SERVIDOR>:80
./scripts/run_direct_benchmark.sh numbered   50 http://<IP_SERVIDOR>:80
./scripts/run_contention_benchmark.sh direct 50  http://<IP_SERVIDOR>:80

# Indirecta (RABBITMQ_HOST sobreescribe el localhost por defecto)
RABBITMQ_HOST=<IP_SERVIDOR> ./scripts/run_indirect_benchmark.sh unnumbered 50
RABBITMQ_HOST=<IP_SERVIDOR> ./scripts/run_indirect_benchmark.sh numbered   50
RABBITMQ_HOST=<IP_SERVIDOR> ./scripts/run_contention_benchmark.sh indirect 50
```

### Máquina cliente: tests y plots

Los tests son unitarios puros — no necesitan el servidor activo:

```bash
./scripts/run_tests.sh
```

Los plots se generan localmente a partir de los JSON guardados en el cliente:

```bash
python3 scripts/plot_results.py
```

### Variables de entorno configurables (indirecta)

| Variable          | Valor por defecto | Descripción              |
|-------------------|-------------------|--------------------------|
| `RABBITMQ_HOST`   | `localhost`       | Dirección del servidor   |
| `RABBITMQ_PORT`   | `5672`            | Puerto AMQP              |
| `RABBITMQ_USER`   | `guest`           | Usuario RabbitMQ         |
| `RABBITMQ_PASS`   | `guest`           | Contraseña RabbitMQ      |
| `RABBITMQ_VHOST`  | `/`               | Virtual host             |

## Estructura de resultados

- Direct:
	- `results/direct/unnumbered/*.json`
	- `results/direct/numbered/*.json`
	- `results/direct/numbered/contention/*.json`
- Indirect:
	- `results/indirect/unnumbered/*.json`
	- `results/indirect/numbered/*.json`
	- `results/indirect/numbered/contention/*.json`
- Tests:
	- `results/tests/*`
- Plots:
	- Estándar:
		- `results/plots/throughput_vs_concurrency_direct.png`
		- `results/plots/throughput_vs_concurrency_indirect.png`
		- `results/plots/numbered_vs_unnumbered_direct.png`
		- `results/plots/numbered_vs_unnumbered_indirect.png`
		- `results/plots/direct_vs_indirect_unnumbered.png`
		- `results/plots/direct_vs_indirect_numbered.png`
		- `results/plots/latency_p95_comparison_unnumbered.png`
		- `results/plots/latency_p95_comparison_numbered.png`
	- Contención (solo se genera cuando existe JSON de contención):
		- `results/plots/direct_vs_indirect_contention_numbered.png`
		- `results/plots/latency_p95_comparison_contention_numbered.png`

## Inicio rápido

1. Configura el entorno Docker:

```bash
./scripts/setup_docker.sh
```

2. Ejecuta la matriz completa de benchmark:

```bash
./scripts/run_all_benchmarks.sh
```

3. Ejecuta tests y guarda artefactos:

```bash
./scripts/run_tests.sh
```

4. Genera plots:

```bash
python3 scripts/plot_results.py
```

5. Inspecciona resúmenes de benchmark:

```bash
find results/direct results/indirect -type f -name "*.json"
jq '.summary' results/direct/unnumbered/*.json | head -40
jq '.summary' results/indirect/numbered/contention/*.json | head -40
```

## Nota sobre el generador de alta contención

`generate_contention_benchmark.py` no es redundante: existe específicamente para cubrir el escenario de alta contención requerido. No reemplaza los ficheros estándar de benchmark; crea una carga sintética adicional para el análisis.
