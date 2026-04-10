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

- `src/`: application code
  - `src/backend/`: consistency and ticket logic (shared by both architectures)
  - `src/direct/`: API server + client + load-balancing components
  - `src/indirect/`: queue config + producer + worker pool
  - `src/experiments/`: benchmark runners and metrics helpers
- `docker/`: compose files and Dockerfiles for direct and indirect stacks
- `benchmarks/`: fixed benchmark input files
- `results/`: output artifacts
  - `results/direct/numbered/`
  - `results/direct/unnumbered/`
  - `results/indirect/numbered/`
  - `results/indirect/unnumbered/`
  - `results/tests/`
  - `results/plots/`
- `scripts/`: setup, benchmark orchestration, plotting, and test scripts
- `tests/`: unit/integration-style tests for core modules
- `docs/`: requirements and work plan

## Main Scripts

- `scripts/setup_docker.sh`
  - Verifies/installs Docker + Compose, fixes permissions, checks daemon access.

- `scripts/run_all_benchmarks.sh`
  - Main benchmark entrypoint.
  - Runs matrix for both architectures and both ticket types over concurrencies:
    `1 2 4 8 16 32 50`.
  - Stores JSON results in the typed folder structure under `results/`.

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
  - Generates plots in `results/plots/`.

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

Then run benchmark using that file (example direct):

```bash
python3 -m src.main \
  --mode benchmark-direct \
  --ticket-type numbered \
  --workload benchmarks/benchmark_numbered_contention.txt \
  --concurrent-clients 50 \
  --api-url http://localhost:80 \
  --output results/direct/numbered/contention_c50_$(date +%Y%m%d_%H%M%S).json
```

## Results Layout

- Direct:
  - `results/direct/unnumbered/*.json`
  - `results/direct/numbered/*.json`
- Indirect:
  - `results/indirect/unnumbered/*.json`
  - `results/indirect/numbered/*.json`
- Tests:
  - `results/tests/*`
- Plots:
  - `results/plots/*.png`

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
```

## Note On High-Contention Generator

`generate_contention_benchmark.py` is not redundant: it exists specifically to satisfy the high-contention requirement scenario. It does not replace standard benchmark files; it creates an additional synthetic workload for analysis.