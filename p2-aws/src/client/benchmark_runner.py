#!/usr/bin/env python3
"""
Main benchmark entry point.
Usage:
  python benchmark_runner.py --mode elastic --type unnumbered
  python benchmark_runner.py --mode stress --type numbered
  python benchmark_runner.py --mode hotspot --type numbered
"""
import argparse
import json
import os
import time
import pika
import boto3
from workload_generator import WorkloadGenerator, DEFAULT_WORKLOAD, STRESS_WORKLOAD

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin123")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "ticket_requests")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
RESULTS_DIR = os.environ.get("RESULTS_DIR", "results")


def _make_pika_channel():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
    )
    ch = conn.channel()
    ch.queue_declare(queue=RABBITMQ_QUEUE, durable=True)
    return conn, ch


def _rabbitmq_sender(ch):
    def send(msg: dict):
        ch.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(msg).encode(),
            properties=pika.BasicProperties(delivery_mode=2, message_id=msg["request_id"]),
        )
    return send


def run_experiment(mode: str, ticket_type: str, hotspot: bool, workers: int = None):
    os.makedirs(RESULTS_DIR, exist_ok=True)

    conn, ch = _make_pika_channel()
    send_fn = _rabbitmq_sender(ch)

    workload = STRESS_WORKLOAD if mode == "stress" else DEFAULT_WORKLOAD
    gen = WorkloadGenerator(
        send_fn=send_fn,
        ticket_type=ticket_type,
        hotspot=hotspot,
        workload=workload,
    )

    experiment_start = time.time()
    events = gen.run()
    experiment_end = time.time()
    conn.close()

    result = {
        "mode": mode,
        "ticket_type": ticket_type,
        "hotspot": hotspot,
        "workers": workers,
        "experiment_start": experiment_start,
        "experiment_end": experiment_end,
        "total_sent": len(events),
        "events": events,
    }

    fname = f"{RESULTS_DIR}/{mode}_{ticket_type}_{'hotspot' if hotspot else 'uniform'}_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Results saved to {fname}")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["elastic", "stress", "hotspot"], default="elastic")
    parser.add_argument("--type", choices=["unnumbered", "numbered"], default="unnumbered", dest="ticket_type")
    parser.add_argument("--hotspot", action="store_true")
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    run_experiment(
        mode=args.mode,
        ticket_type=args.ticket_type,
        hotspot=args.hotspot or args.mode == "hotspot",
        workers=args.workers,
    )
