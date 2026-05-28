#!/bin/bash
# Runs the full experiment matrix:
#   1. Calibrate worker capacity (C) with single worker
#   2. Stress test (gradually increase load until saturation)
#   3. Elastic workload Z(t) - uniform
#   4. Elastic workload Z(t) - hotspot (80% on 5% of seats)
# Results saved to results/
set -e

RESULTS_DIR=${RESULTS_DIR:-results}
mkdir -p "$RESULTS_DIR"

cd "$(dirname "$0")/../src/client"

echo "=== Experiment 1: Calibration (1 worker) ==="
# Fix Lambda concurrency to 1, measure capacity C
python3 -c "
import boto3, os, time
lam = boto3.client('lambda', region_name=os.environ.get('AWS_DEFAULT_REGION','us-east-1'))
lam.put_function_concurrency(FunctionName=os.environ['LAMBDA_FUNCTION_NAME'], ReservedConcurrentExecutions=1)
print('Set Lambda concurrency = 1')
time.sleep(2)
"
python3 benchmark_runner.py --mode stress --type unnumbered
echo "Calibration done."

echo ""
echo "=== Experiment 2: Stress test ==="
python3 benchmark_runner.py --mode stress --type unnumbered
python3 benchmark_runner.py --mode stress --type numbered

echo ""
echo "=== Experiment 3: Elastic workload - unnumbered ==="
# Start scaler in background
python3 ../scaling/scaler.py &
SCALER_PID=$!

python3 benchmark_runner.py --mode elastic --type unnumbered
kill $SCALER_PID 2>/dev/null

echo ""
echo "=== Experiment 4: Elastic workload - numbered uniform ==="
python3 ../scaling/scaler.py &
SCALER_PID=$!

python3 benchmark_runner.py --mode elastic --type numbered
kill $SCALER_PID 2>/dev/null

echo ""
echo "=== Experiment 5: Hotspot - numbered ==="
python3 ../scaling/scaler.py &
SCALER_PID=$!

python3 benchmark_runner.py --mode hotspot --type numbered --hotspot
kill $SCALER_PID 2>/dev/null

echo ""
echo "=== All experiments complete ==="
echo "Results in $RESULTS_DIR/"
echo ""
echo "To analyze and plot:"
echo "  cd src/metrics"
echo "  python analyzer.py --start <epoch> --end <epoch> --output results/analysis.json"
echo "  python plotter.py results/analysis_*.json"
