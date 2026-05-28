#!/usr/bin/env python3
"""
Dynamic scaling controller (post-SQS-pivot).

Polls RabbitMQ queue depth, applies the elasticity formula
    N = (B + lambda_rate * Tr) / (C * Tr)
and converges the number of alive Lambda workers to N by either:
  * invoking new Lambdas (boto3 invoke InvocationType=Event), or
  * publishing QUIT control messages to the same queue (each Lambda exits
    when it consumes one).

Tracks alive workers locally — Lambdas also self-exit on idle timeout so
the local count is a soft target rather than an exact contract.

Run on any machine with AWS credentials + network access to RabbitMQ.
Designed to be started alongside the benchmark.
"""
import json
import math
import os
import time
import boto3
import pika
import uuid

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
LAMBDA_FUNCTION_NAME = os.environ["LAMBDA_FUNCTION_NAME"]
RABBITMQ_HOST = os.environ["RABBITMQ_HOST"]
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin123")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "ticket_requests")

C = float(os.environ.get("WORKER_CAPACITY", "8"))
Tr = float(os.environ.get("TARGET_RESPONSE_S", "2"))
MIN_WORKERS = int(os.environ.get("MIN_WORKERS", "0"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "20"))
POLL_INTERVAL_S = float(os.environ.get("POLL_INTERVAL_S", "5"))

lam = boto3.client("lambda", region_name=AWS_REGION)
cw = boto3.client("cloudwatch", region_name=AWS_REGION)

_last_backlog = 0
_last_time = time.time()
_alive = 0  # local estimate of live workers


def _rabbit_channel():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST, credentials=creds, heartbeat=60
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=RABBITMQ_QUEUE, passive=True)
    return conn, ch


def _queue_depth(ch) -> int:
    """Use queue_declare(passive=True) to get message count cheaply."""
    res = ch.queue_declare(queue=RABBITMQ_QUEUE, passive=True)
    return res.method.message_count


def _estimate_rate(backlog: int) -> float:
    global _last_backlog, _last_time
    now = time.time()
    dt = now - _last_time
    if dt < 0.1:
        return 0.0
    delta = backlog - _last_backlog
    _last_backlog = backlog
    _last_time = now
    return max(0.0, delta / dt)


def _compute_n(backlog: int, rate: float) -> int:
    n = (backlog + rate * Tr) / (C * Tr)
    return max(MIN_WORKERS, min(MAX_WORKERS, math.ceil(n)))


def _invoke_workers(k: int):
    for _ in range(k):
        lam.invoke(
            FunctionName=LAMBDA_FUNCTION_NAME,
            InvocationType="Event",
            Payload=json.dumps({"worker_id": uuid.uuid4().hex[:8]}).encode(),
        )


def _send_quits(ch, k: int):
    body = json.dumps({"action": "quit"}).encode()
    for _ in range(k):
        ch.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2, priority=255),
        )


def _put_metric(n: int, backlog: int, rate: float):
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
    global _alive
    print(f"Scaler started. C={C} msg/s, Tr={Tr}s, min={MIN_WORKERS}, max={MAX_WORKERS}")

    conn, ch = _rabbit_channel()
    try:
        while True:
            try:
                backlog = _queue_depth(ch)
                rate = _estimate_rate(backlog)
                target = _compute_n(backlog, rate)

                if target > _alive:
                    add = target - _alive
                    print(f"Scale UP {_alive} -> {target} (B={backlog}, rate={rate:.1f}/s) invoking {add}")
                    _invoke_workers(add)
                    _alive = target
                elif target < _alive:
                    drop = _alive - target
                    print(f"Scale DOWN {_alive} -> {target} (B={backlog}, rate={rate:.1f}/s) sending {drop} QUITs")
                    _send_quits(ch, drop)
                    _alive = target

                _put_metric(_alive, backlog, rate)
            except (pika.exceptions.AMQPError, pika.exceptions.ConnectionClosed) as e:
                print(f"RabbitMQ error: {e} — reconnecting in 5s")
                try:
                    conn.close()
                except Exception:
                    pass
                time.sleep(5)
                conn, ch = _rabbit_channel()
            except Exception as e:
                print(f"Scaler error: {e}")

            time.sleep(POLL_INTERVAL_S)
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    run()
