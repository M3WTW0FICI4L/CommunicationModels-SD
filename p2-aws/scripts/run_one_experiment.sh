#!/bin/bash
# Run one experiment on the RabbitMQ EC2.
# Usage: ./run_one_experiment.sh <mode> <type> <hotspot 0|1> <pg_host> <lambda_name>
# Starts the scaler in background, runs the workload, waits for drain,
# stops the scaler, returns counts.
set -e
MODE=$1
TYPE=$2
HOTSPOT=$3
PG_HOST=$4
LAMBDA_NAME=$5

cd ~/client

export RABBITMQ_HOST=localhost
export RABBITMQ_USER=admin
export RABBITMQ_PASS=admin123
export RABBITMQ_QUEUE=ticket_requests
export PG_HOST=$PG_HOST
export PG_PORT=5432
export PG_DB=tickets
export PG_USER=ticket_user
export PG_PASS=ticket_pass
export LAMBDA_FUNCTION_NAME=$LAMBDA_NAME
export AWS_REGION=us-east-1
export WORKER_CAPACITY=8
export TARGET_RESPONSE_S=2
export MIN_WORKERS=0
export MAX_WORKERS=20
export POLL_INTERVAL_S=5
export PYTHONUNBUFFERED=1
export RESULTS_DIR=~/results

echo "=== Resetting DB ==="
PGPASSWORD=ticket_pass psql -h $PG_HOST -U ticket_user -d tickets -c "TRUNCATE TABLE tickets; UPDATE ticket_counter SET sold=0;"

echo "=== Starting scaler ==="
nohup python3 scaler.py > ~/results/scaler_${MODE}_${TYPE}.log 2>&1 &
SCALER_PID=$!
sleep 2

echo "=== Running workload [$MODE / $TYPE / hotspot=$HOTSPOT] ==="
ARGS="--mode $MODE --type $TYPE"
[ "$HOTSPOT" = "1" ] && ARGS="$ARGS --hotspot"
python3 benchmark_runner.py $ARGS

echo "=== Waiting for drain ==="
EXPECTED=$(ls -t ~/results/*.json 2>/dev/null | head -1 | xargs -I{} grep -o '"total_sent": [0-9]*' {} | awk '{print $2}')
echo "Expected $EXPECTED tickets in DB"
START=$(date +%s)
while true; do
  N=$(PGPASSWORD=ticket_pass psql -h $PG_HOST -U ticket_user -d tickets -tAc "SELECT COUNT(*) FROM tickets")
  echo "  drain: $N / $EXPECTED"
  [ "$N" -ge "$EXPECTED" ] && break
  ELAPSED=$(( $(date +%s) - START ))
  [ $ELAPSED -gt 600 ] && echo "  TIMEOUT" && break
  sleep 5
done

echo "=== Stopping scaler ==="
kill $SCALER_PID 2>/dev/null || true
sleep 1

echo "=== Final counts ==="
PGPASSWORD=ticket_pass psql -h $PG_HOST -U ticket_user -d tickets -c "SELECT status, COUNT(*) FROM tickets GROUP BY status ORDER BY status;"

echo "=== DONE ==="
