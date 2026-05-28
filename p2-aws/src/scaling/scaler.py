#!/usr/bin/env python3
"""
Dynamic scaling controller.
Polls SQS queue depth and adjusts Lambda reserved concurrency using:
  N = (B + lambda_rate * Tr) / (C * Tr)

Run on any machine with AWS credentials. Typically started alongside the benchmark.
"""
import os
import time
import math
import boto3

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
LAMBDA_FUNCTION_NAME = os.environ["LAMBDA_FUNCTION_NAME"]

# Scaling parameters (calibrated experimentally)
C = float(os.environ.get("WORKER_CAPACITY", "8"))    # processed msgs/s per Lambda concurrency unit
Tr = float(os.environ.get("TARGET_RESPONSE_S", "1")) # target response time in seconds
MIN_WORKERS = int(os.environ.get("MIN_WORKERS", "1"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "50"))
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "5"))

sqs = boto3.client("sqs", region_name=AWS_REGION)
lam = boto3.client("lambda", region_name=AWS_REGION)
cw = boto3.client("cloudwatch", region_name=AWS_REGION)

_last_backlog = 0
_last_time = time.time()


def _get_queue_depth() -> int:
    resp = sqs.get_queue_attributes(
        QueueUrl=SQS_QUEUE_URL,
        AttributeNames=["ApproximateNumberOfMessages", "ApproximateNumberOfMessagesNotVisible"],
    )
    attrs = resp["Attributes"]
    visible = int(attrs.get("ApproximateNumberOfMessages", 0))
    in_flight = int(attrs.get("ApproximateNumberOfMessagesNotVisible", 0))
    return visible + in_flight


def _estimate_arrival_rate(backlog: int) -> float:
    """Estimate λ from the change in backlog over the poll interval."""
    global _last_backlog, _last_time
    now = time.time()
    dt = now - _last_time
    if dt < 0.1:
        return 0.0
    # Arrival rate ≈ (new_backlog - old_backlog) / dt  (rough estimate)
    # In practice we'd use CloudWatch NumberOfMessagesSent metric for accuracy
    delta = backlog - _last_backlog
    _last_backlog = backlog
    _last_time = now
    return max(0.0, delta / dt)


def _compute_n(backlog: int, arrival_rate: float) -> int:
    """N = (B + λ * Tr) / (C * Tr)"""
    n = (backlog + arrival_rate * Tr) / (C * Tr)
    return max(MIN_WORKERS, min(MAX_WORKERS, math.ceil(n)))


def _set_lambda_concurrency(n: int):
    lam.put_function_concurrency(
        FunctionName=LAMBDA_FUNCTION_NAME,
        ReservedConcurrentExecutions=n,
    )


def _put_scaling_metric(n: int, backlog: int, rate: float):
    try:
        cw.put_metric_data(
            Namespace="TicketService",
            MetricData=[
                {"MetricName": "TargetWorkers", "Value": float(n), "Unit": "Count"},
                {"MetricName": "QueueBacklog", "Value": float(backlog), "Unit": "Count"},
                {"MetricName": "ArrivalRate", "Value": rate, "Unit": "Count/Second"},
            ],
        )
    except Exception:
        pass


def run():
    print(f"Scaler started. C={C} msg/s, Tr={Tr}s, min={MIN_WORKERS}, max={MAX_WORKERS}")
    current_n = MIN_WORKERS
    _set_lambda_concurrency(current_n)

    while True:
        try:
            backlog = _get_queue_depth()
            rate = _estimate_arrival_rate(backlog)
            target_n = _compute_n(backlog, rate)

            if target_n != current_n:
                print(f"Scaling: {current_n} → {target_n}  (B={backlog}, λ={rate:.1f}/s)")
                _set_lambda_concurrency(target_n)
                current_n = target_n

            _put_scaling_metric(current_n, backlog, rate)
        except Exception as e:
            print(f"Scaler error: {e}")

        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    run()
