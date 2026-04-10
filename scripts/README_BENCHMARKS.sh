#!/usr/bin/env bash
# Quick reference guide for running benchmarks

cat << 'EOF'

╔════════════════════════════════════════════════════════════════════════════╗
║              Benchmark Scripts - Quick Reference Guide                     ║
╚════════════════════════════════════════════════════════════════════════════╝

## 📋 Available Scripts

### 1. setup_docker.sh
   Purpose: Ensure Docker and Docker Compose are installed and running
   Usage:   ./scripts/setup_docker.sh
   Does:
     - Detects OS and installs Docker if missing
     - Installs Docker Compose if missing
     - Starts Docker daemon
     - Sets up user permissions
     - Validates everything is working
   
   Run once at the beginning to ensure Docker is ready.

### 2. run_direct_benchmark.sh
   Purpose: Run benchmark against Direct (REST) architecture
   Usage:   ./scripts/run_direct_benchmark.sh [ticket_type] [concurrency] [api_url]
   
   Arguments:
     ticket_type    : unnumbered (default) or numbered
     concurrency    : number of concurrent clients (default: 50)
     api_url        : API endpoint (default: http://localhost:80)
   
   Examples:
     ./scripts/run_direct_benchmark.sh
     ./scripts/run_direct_benchmark.sh unnumbered 50 http://localhost:80
     ./scripts/run_direct_benchmark.sh numbered 100 http://localhost:8000
   
   Requirements:
     - FastAPI server running (via Docker or local)
     - Redis backend running
   
   Output: JSON results in results/direct/

### 3. run_indirect_benchmark.sh
   Purpose: Run benchmark against Indirect (RabbitMQ) architecture
   Usage:   ./scripts/run_indirect_benchmark.sh [ticket_type] [concurrency]
   
   Arguments:
     ticket_type    : unnumbered (default) or numbered
     concurrency    : number of concurrent clients (default: 50)
   
   Examples:
     ./scripts/run_indirect_benchmark.sh
     ./scripts/run_indirect_benchmark.sh unnumbered 50
     ./scripts/run_indirect_benchmark.sh numbered 100
   
   Requirements:
     - RabbitMQ server running
     - Redis backend running
     - Worker processes running
   
   Output: JSON results in results/indirect/

### 4. scalability_sweep.sh
   Purpose: Test Direct architecture scalability with multiple client counts
   Usage:   ./scripts/scalability_sweep.sh [api_url]
   
   Arguments:
     api_url        : API endpoint (default: http://localhost:80)
   
   Features:
     - Tests concurrency levels: 1, 2, 4, 8, 16, 32
     - Tests both unnumbered and numbered tickets
     - Resets state between runs
     - Generates 12 JSON result files
   
   Examples:
     ./scripts/scalability_sweep.sh
     ./scripts/scalability_sweep.sh http://localhost:8000
   
   Requirements:
     - FastAPI server running
     - Redis backend running
   
   Output: Multiple JSON files in results/direct/

### 5. run_all_benchmarks.sh (★ RECOMMENDED)
   Purpose: Complete end-to-end benchmark orchestration
   Usage:   ./scripts/run_all_benchmarks.sh [skip_docker] [skip_direct] [skip_indirect]
   
   Arguments:
     skip_docker    : true to skip Docker setup (default: false)
     skip_direct    : true to skip Direct benchmarks (default: false)
     skip_indirect  : true to skip Indirect benchmarks (default: false)
   
   Does:
     1. Ensures Docker is installed and running
     2. Launches Direct architecture (API + Redis + Nginx)
     3. Runs Direct benchmarks (unnumbered + numbered)
     4. Stops Direct architecture
     5. Launches Indirect architecture (RabbitMQ + Redis + 4 workers)
     6. Runs Indirect benchmarks (unnumbered + numbered)
     7. Stops Indirect architecture
     8. Summarizes results
   
   Examples:
     ./scripts/run_all_benchmarks.sh        # Full run
     ./scripts/run_all_benchmarks.sh true   # Skip Docker setup
     ./scripts/run_all_benchmarks.sh true true  # Only Indirect benchmarks
   
   Output: 
     - Automatically starts and stops Docker services
     - JSON results in results/direct/ and results/indirect/
     - Console summary at the end

### 6. run_tests.sh
   Purpose: Run unit tests with coverage
   Usage:   ./scripts/run_tests.sh
   Output:  HTML coverage report in htmlcov/

### 7. plot_results.py
   Purpose: Generate plots from benchmark results
   Usage:   python3 scripts/plot_results.py
   Input:   JSON files in results/direct/ and results/indirect/
   Output:  PNG plots in results/plots/

### 8. generate_contention_benchmark.py
   Purpose: Generate custom contention benchmark workloads
   Usage:   python3 scripts/generate_contention_benchmark.py
   Output:  Custom benchmark files

═══════════════════════════════════════════════════════════════════════════════

## 🚀 Quick Start Scenarios

### Scenario A: Full Automated Benchmark
   Purpose: Run everything with automatic Docker management
   
   $ ./scripts/run_all_benchmarks.sh
   
   Time: ~5-10 minutes (depending on hardware)
   Output: All JSON results + console summary

### Scenario B: Docker Already Running
   Purpose: Skip Docker setup, run benchmarks on existing services
   
   # Manually start services:
   $ docker compose -f docker/docker-compose.direct.yml up -d --build
   $ docker compose -f docker/docker-compose.indirect.yml up -d --build --scale worker=4
   
   # Run individual benchmarks:
   $ ./scripts/run_direct_benchmark.sh unnumbered 50
   $ ./scripts/run_indirect_benchmark.sh unnumbered 50
   
   # Or use orchestration:
   $ ./scripts/run_all_benchmarks.sh true true false  # Skip Docker + Direct, only Indirect

### Scenario C: Local Development
   Purpose: Test with non-Docker services
   
   # Terminal 1: Start Direct API
   $ python3 -m src.main --mode direct-api --host 0.0.0.0 --port 8000
   
   # Terminal 2: Start Indirect Workers
   $ python3 -m src.main --mode indirect-worker --workers 4 --worker-id worker-1
   
   # Terminal 3: Run benchmarks
   $ ./scripts/run_direct_benchmark.sh unnumbered 50 http://localhost:8000
   $ ./scripts/run_indirect_benchmark.sh unnumbered 50

### Scenario D: Multiple Runs for Statistics
   Purpose: Run benchmarks multiple times to collect statistics
   
   for i in {1..3}; do
       echo "Run $i..."
       ./scripts/run_all_benchmarks.sh true true  # Skip Docker setup between runs
       sleep 10
   done

═══════════════════════════════════════════════════════════════════════════════

## 📊 Understanding Results

### Direct Results (results/direct/*.json)
   {
     "summary": {
       "total_time_s": 29.251,
       "total_requests": 20000,
       "successful_requests": 20000,
       "failed_requests": 0,
       "throughput_rps": 683.73,
       "mean_response_time_s": 0.0713,
       "p95_response_time_s": 0.1809,
       "p99_response_time_s": 0.2577,
       "min_response_time_s": 0.0023,
       "max_response_time_s": 0.5448
     },
     "raw": [...]  # List of all individual requests
   }

### Indirect Results (results/indirect/*.json)
   Similar structure to Direct, with additional waiting for worker responses

### Key Metrics:
   - throughput_rps: Requests per second (higher = better)
   - mean_response_time_s: Average latency
   - p95/p99: 95th/99th percentile latencies (tail performance)
   - success rate: % of successful transactions (should be 100%)

═══════════════════════════════════════════════════════════════════════════════

## 🔧 Troubleshooting

### Docker permission denied
   $ ./scripts/setup_docker.sh
   (Follow instructions to add user to docker group)

### API not reachable
   $ curl http://localhost:80/health
   (If fails, ensure docker containers are running:)
   $ docker compose -f docker/docker-compose.direct.yml ps

### RabbitMQ connection timeout
   $ docker compose -f docker/docker-compose.indirect.yml ps
   (Ensure rabbitmq and worker containers are healthy)

### Benchmark hangs or times out
   Check if system has sufficient resources:
   $ docker stats
   (Kill and restart with fewer concurrent clients:)
   $ ./scripts/run_indirect_benchmark.sh unnumbered 10

═══════════════════════════════════════════════════════════════════════════════

## 📈 After Benchmarks

1. View results:
   $ ls -lh results/direct/*.json results/indirect/*.json

2. Analyze summary:
   $ jq '.summary' results/direct/unnumbered_c50_*.json

3. Generate plots:
   $ python3 scripts/plot_results.py

4. Compare architectures:
   $ python3 << 'PYTHON'
   import json
   import glob
   
   # Load most recent results
   direct_files = sorted(glob.glob('results/direct/*.json'))[-2:]
   indirect_files = sorted(glob.glob('results/indirect/*.json'))[-2:]
   
   print("DIRECT THROUGHPUT:")
   for f in direct_files:
       data = json.load(open(f))
       print(f"  {f}: {data['summary']['throughput_rps']} rps")
   
   print("\nINDIRECT THROUGHPUT:")
   for f in indirect_files:
       data = json.load(open(f))
       print(f"  {f}: {data['summary']['throughput_rps']} rps")
   PYTHON

═══════════════════════════════════════════════════════════════════════════════

EOF
