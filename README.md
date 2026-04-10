# CommunicationModels-SD

Scalable ticket acquisition system to compare direct vs indirect middleware under high load and contention.

[![codecov](https://codecov.io/gh/M3WTW0FICI4L/CommunicationModels-SD/graph/badge.svg?token=QV602QYGAO)](https://codecov.io/gh/M3WTW0FICI4L/CommunicationModels-SD)

## What This Project Implements

- Two ticket models:
  - `unnumbered` (max 20,000 sales)
  - `numbered` (seat `1..20000`, no double-sell)
- Two communication architectures:
  - Direct: REST API + NGINX load balancer + Redis
  - Indirect: RabbitMQ + workers + Redis
- Shared correctness core in `src/backend`

## Repository Structure

  - `src/backend/`: consistency and ticket logic (shared by both architectures)
  - `src/direct/`: API server + client + load-balancing components
  - `src/indirect/`: queue config + producer + worker pool
  - `src/experiments/`: benchmark runners and metrics helpers
  - `results/direct/numbered/`
  - `results/direct/numbered/contention/`
  - `results/direct/unnumbered/`
  - `results/indirect/numbered/`
  - `results/indirect/numbered/contention/`
  - `results/indirect/unnumbered/`
  - `results/tests/`
  - `results/plots/`

- `scripts/`: setup, benchmark orchestration, plotting, and test scripts
- `tests/`: unit/integration-style tests for core modules
  - Verifies/installs Docker + Compose, fixes permissions, checks daemon access.

- `scripts/run_all_benchmarks.sh`
  - Main benchmark entrypoint.
  - Runs matrix for both architectures and both ticket types over concurrencies:
    `1 2 4 8 16 32 50`.
  - Also runs a **high-contention matrix** (numbered only) for both architectures.
  - Stores JSON results in the typed folder structure under `results/`.
  - Optional 4th argument `SERVER_HOST`: when set to a non-localhost address, skips local Docker lifecycle and targets a remote server.

- `scripts/run_contention_benchmark.sh`
  - Single high-contention run for the `numbered` model.
  - Supports both architectures:
    - `./scripts/run_contention_benchmark.sh direct <concurrency> <api_url>`
    - `./scripts/run_contention_benchmark.sh indirect <concurrency>`
  - Stores JSON in:
    - `results/direct/numbered/contention/`
    - `results/indirect/numbered/contention/`

- `scripts/run_direct_benchmark.sh`
  - Single direct benchmark run for one ticket type and one concurrency.

- `scripts/run_indirect_benchmark.sh`
  - Single indirect benchmark run for one ticket type and one concurrency.

- `scripts/run_tests.sh`
  - Runs test suite with coverage.
  - Saves artifacts under `results/tests/`:
    - pytest log
    - JUnit XML
    - timestamped HTML coverage folder

- `scripts/plot_results.py`
  - Loads benchmark JSON recursively from `results/direct/**` and `results/indirect/**`.
  - Generates standard plots in `results/plots/`.
  - Generates contention comparison plots when contention data exists:
    - `direct_vs_indirect_contention_numbered.png`
    - `latency_p95_comparison_contention_numbered.png`

- `scripts/generate_contention_benchmark.py`
  - Generates a numbered high-contention workload (80% of traffic against 5% of seats).
  - Use this to run the additional contention experiments requested in requirements.

## Where `generate_contention_benchmark` Writes Output

By default, it writes to:

- `benchmarks/benchmark_numbered_contention.txt`

You can change it with `--output`:

```bash
python3 scripts/generate_contention_benchmark.py \
  --output benchmarks/my_custom_contention.txt \
  --total 60000
```

The generated file format is compatible with the numbered benchmark parser:

- `BUY <client_id> <seat_id> <request_id>`

## How To Run Tests

Recommended (stores all artifacts in `results/tests/`):

```bash
./scripts/run_tests.sh
```

Artifacts produced:

- `results/tests/pytest_<timestamp>.log`
- `results/tests/junit_<timestamp>.xml`
- `results/tests/htmlcov_<timestamp>/index.html`

Optional direct pytest commands:

```bash
pytest -v
pytest tests/test_models.py -v
pytest tests/test_ticket_manager.py::TestTicketManagerInitialization::test_ticket_manager_initialization -v
```

## How To Run Benchmarks

### A) Full matrix (recommended)

Runs direct and indirect for both ticket types with concurrencies:

- `1 2 4 8 16 32 50`

Command:

```bash
./scripts/run_all_benchmarks.sh
```

If Docker is already configured and you want to skip setup:

```bash
./scripts/run_all_benchmarks.sh true
```

To run against a remote server (see [Running on Two Machines](#running-on-two-machines)):

```bash
./scripts/run_all_benchmarks.sh true false false <SERVER_IP>
```

### B) Individual runs

Direct single run:

```bash
./scripts/run_direct_benchmark.sh unnumbered 50 http://localhost:80
./scripts/run_direct_benchmark.sh numbered 50 http://localhost:80
```

Indirect single run:

```bash
./scripts/run_indirect_benchmark.sh unnumbered 50
./scripts/run_indirect_benchmark.sh numbered 50
```

### C) High-contention scenario

Generate contention workload (80/5):

```bash
python3 scripts/generate_contention_benchmark.py \
  --output benchmarks/benchmark_numbered_contention.txt \
  --total 60000
```

Run a single high-contention benchmark with the dedicated script:

```bash
./scripts/run_contention_benchmark.sh direct 50 http://localhost:80
./scripts/run_contention_benchmark.sh indirect 50
```

Or run the complete matrix (including contention) with:

```bash
./scripts/run_all_benchmarks.sh
```

If you prefer invoking the benchmark module manually (example direct):

```bash
python3 -m src.main \
  --mode benchmark-direct \
  --ticket-type numbered \
  --workload benchmarks/benchmark_numbered_contention.txt \
  --concurrent-clients 50 \
  --api-url http://localhost:80 \
  --output results/direct/numbered/contention/c50_$(date +%Y%m%d_%H%M%S).json
```

## Running on Two Machines

One machine acts as **server** (runs Docker + containers) and the other as **client** (runs benchmarks, tests and plots). Both must be reachable on the same network.

Required ports open on the server:

| Port  | Service            | Architecture |
|-------|--------------------|--------------|
| 80    | NGINX (REST API)   | Direct       |
| 5672  | RabbitMQ AMQP      | Indirect     |
| 15672 | RabbitMQ UI (opt.) | Indirect     |

### Server machine: start the architecture

```bash
# Direct
docker compose -f docker/docker-compose.direct.yml up -d --build

# Indirect
docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4
```

### Client machine: run benchmarks

**Option A — orchestrator script (4th argument = server IP):**

```bash
# Direct benchmarks only
./scripts/run_all_benchmarks.sh true false true <SERVER_IP>

# Indirect benchmarks only
./scripts/run_all_benchmarks.sh true true false <SERVER_IP>

# Both (server must have both stacks running simultaneously)
./scripts/run_all_benchmarks.sh true false false <SERVER_IP>
```

**Option B — individual scripts:**

```bash
# Direct
./scripts/run_direct_benchmark.sh unnumbered 50 http://<SERVER_IP>:80
./scripts/run_direct_benchmark.sh numbered   50 http://<SERVER_IP>:80
./scripts/run_contention_benchmark.sh direct 50  http://<SERVER_IP>:80

# Indirect (RABBITMQ_HOST overrides the default localhost)
RABBITMQ_HOST=<SERVER_IP> ./scripts/run_indirect_benchmark.sh unnumbered 50
RABBITMQ_HOST=<SERVER_IP> ./scripts/run_indirect_benchmark.sh numbered   50
RABBITMQ_HOST=<SERVER_IP> ./scripts/run_contention_benchmark.sh indirect 50
```

### Client machine: tests and plots

Tests are pure unit tests — no live server needed:

```bash
./scripts/run_tests.sh
```

Plots are generated locally from the JSON results saved on the client:

```bash
python3 scripts/plot_results.py
```

### Configurable environment variables (indirect)

| Variable          | Default     | Description             |
|-------------------|-------------|-------------------------|
| `RABBITMQ_HOST`   | `localhost` | RabbitMQ server address |
| `RABBITMQ_PORT`   | `5672`      | AMQP port               |
| `RABBITMQ_USER`   | `guest`     | RabbitMQ user           |
| `RABBITMQ_PASS`   | `guest`     | RabbitMQ password       |
| `RABBITMQ_VHOST`  | `/`         | Virtual host            |

## Results Layout

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
  - Standard:
    - `results/plots/throughput_vs_concurrency_direct.png`
    - `results/plots/throughput_vs_concurrency_indirect.png`
    - `results/plots/numbered_vs_unnumbered_direct.png`
    - `results/plots/numbered_vs_unnumbered_indirect.png`
    - `results/plots/direct_vs_indirect_unnumbered.png`
    - `results/plots/direct_vs_indirect_numbered.png`
    - `results/plots/latency_p95_comparison_unnumbered.png`
    - `results/plots/latency_p95_comparison_numbered.png`
  - Contention (generated only when contention JSON exists):
    - `results/plots/direct_vs_indirect_contention_numbered.png`
    - `results/plots/latency_p95_comparison_contention_numbered.png`

## Quick Start

1. Set up Docker environment:

```bash
./scripts/setup_docker.sh
```

2. Run full benchmark matrix:

```bash
./scripts/run_all_benchmarks.sh
```

3. Run tests and store artifacts:

```bash
./scripts/run_tests.sh
```

4. Generate plots:

```bash
python3 scripts/plot_results.py
```

5. Inspect benchmark summaries:

```bash
find results/direct results/indirect -type f -name "*.json"
jq '.summary' results/direct/unnumbered/*.json | head -40
jq '.summary' results/indirect/numbered/contention/*.json | head -40
```

## Note On High-Contention Generator

`generate_contention_benchmark.py` is not redundant: it exists specifically to satisfy the high-contention requirement scenario. It does not replace standard benchmark files; it creates an additional synthetic workload for analysis.