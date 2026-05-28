#!/usr/bin/env python3
"""
Calibration sweep: measure throughput per fixed worker count.

For each N in WORKER_COUNTS the scaler is paused; instead this script
- invokes exactly N Lambda workers (boto3 invoke InvocationType=Event),
- publishes BURST_SIZE messages to RabbitMQ,
- waits for the DB to receive BURST_SIZE rows,
- computes throughput = total / (last_processed - first_processed),
- publishes N QUIT messages so the workers exit cleanly.
"""
import json
import os
import time
import uuid
import boto3
import pika
import psycopg2

LAMBDA = os.environ["LAMBDA_FUNCTION_NAME"]
RABBITMQ_HOST = os.environ["RABBITMQ_HOST"]
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin123")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "ticket_requests")
PG_HOST = os.environ["PG_HOST"]
WORKER_COUNTS = [int(x) for x in os.environ.get("WORKER_COUNTS", "1,2,4,8,16,32").split(",")]
BURST_SIZE = int(os.environ.get("BURST_SIZE", "500"))

lam = boto3.client("lambda", region_name="us-east-1")


def pg():
    return psycopg2.connect(host=PG_HOST, port=5432, dbname="tickets",
                            user="ticket_user", password="ticket_pass")


def reset_db():
    conn = pg()
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE tickets")
    cur.execute("UPDATE ticket_counter SET sold = 0")
    conn.commit()
    conn.close()


def rabbit_channel():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds)
    )
    ch = conn.channel()
    ch.queue_declare(queue=RABBITMQ_QUEUE, passive=True)
    return conn, ch


def burst_publish(ch, n: int):
    for _ in range(n):
        msg = {"request_id": str(uuid.uuid4()), "ticket_type": "unnumbered"}
        ch.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=json.dumps(msg).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )


def send_quits(ch, n: int):
    body = json.dumps({"action": "quit"}).encode()
    for _ in range(n):
        ch.basic_publish(
            exchange="",
            routing_key=RABBITMQ_QUEUE,
            body=body,
            properties=pika.BasicProperties(delivery_mode=2),
        )


def invoke_workers(n: int):
    for _ in range(n):
        lam.invoke(
            FunctionName=LAMBDA,
            InvocationType="Event",
            Payload=json.dumps({"worker_id": uuid.uuid4().hex[:8]}).encode(),
        )


def wait_drain(expected: int, timeout: int = 600) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        conn = pg()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tickets")
        n = cur.fetchone()[0]
        conn.close()
        if n >= expected:
            return True
        time.sleep(2)
    return False


def measure() -> dict:
    conn = pg()
    cur = conn.cursor()
    cur.execute("SELECT MIN(processed_at), MAX(processed_at), COUNT(*) FROM tickets")
    first, last, total = cur.fetchone()
    conn.close()
    if not first or not last or total == 0:
        return {"throughput": 0, "total": 0}
    span = (last - first).total_seconds()
    return {
        "throughput": total / span if span > 0 else 0,
        "total": total,
        "span_s": span,
    }


def main():
    results = {}
    for n in WORKER_COUNTS:
        print(f"\n=== Calibrating N={n} ===")
        reset_db()

        conn, ch = rabbit_channel()
        try:
            print(f"Invoking {n} Lambda workers...")
            invoke_workers(n)
            # Give workers a moment to connect to RabbitMQ before publishing
            time.sleep(3)

            print(f"Publishing burst of {BURST_SIZE} messages to RabbitMQ...")
            t0 = time.time()
            burst_publish(ch, BURST_SIZE)
            print(f"Sent in {time.time() - t0:.1f}s. Waiting for drain...")

            if not wait_drain(BURST_SIZE, timeout=600):
                print(f"  TIMEOUT — only got partial drain")
                send_quits(ch, n)
                continue

            m = measure()
            results[n] = m
            print(f"  Throughput: {m['throughput']:.1f} req/s ({m['total']} in {m['span_s']:.1f}s)")

            # Shut down workers cleanly
            send_quits(ch, n)
            time.sleep(2)
        finally:
            conn.close()

    out = "results/calibration.json"
    os.makedirs("results", exist_ok=True)
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()
