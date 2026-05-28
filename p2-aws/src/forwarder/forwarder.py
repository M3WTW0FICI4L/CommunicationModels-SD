#!/usr/bin/env python3
"""
RabbitMQ → SQS bridge.
Runs as a systemd service on the RabbitMQ EC2.
Reads from RabbitMQ and forwards messages to SQS for Lambda to consume.
"""
import json
import os
import signal
import sys
import time
import boto3
import pika

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin123")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "ticket_requests")
SQS_QUEUE_URL = os.environ["SQS_QUEUE_URL"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", 10))  # SQS send_message_batch max

sqs = boto3.client("sqs", region_name=AWS_REGION)
_running = True


def _connect_rabbitmq():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(host=RABBITMQ_HOST, credentials=creds,
                                       heartbeat=60, blocked_connection_timeout=30)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True,
                          arguments={"x-dead-letter-exchange": "ticket_dlx"})
    return connection, channel


def _flush_to_sqs(batch: list):
    """Send a batch of (delivery_tag, body) to SQS."""
    if not batch:
        return []
    entries = [
        {"Id": str(i), "MessageBody": body, "MessageGroupId": "tickets"}
        if ".fifo" in SQS_QUEUE_URL
        else {"Id": str(i), "MessageBody": body}
        for i, (_, body) in enumerate(batch)
    ]
    resp = sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=entries)
    failed_ids = {f["Id"] for f in resp.get("Failed", [])}
    acked = []
    for i, (tag, _) in enumerate(batch):
        if str(i) not in failed_ids:
            acked.append(tag)
    return acked


def run():
    while _running:
        try:
            conn, channel = _connect_rabbitmq()
            print(f"Connected to RabbitMQ at {RABBITMQ_HOST}", flush=True)
            batch = []

            while _running:
                method, _, body = channel.basic_get(queue=RABBITMQ_QUEUE, auto_ack=False)
                if method is None:
                    # Queue empty — flush whatever we have and wait
                    if batch:
                        acked = _flush_to_sqs(batch)
                        for tag in acked:
                            channel.basic_ack(tag)
                        batch = []
                    time.sleep(0.05)
                    continue

                batch.append((method.delivery_tag, body.decode()))

                if len(batch) >= BATCH_SIZE:
                    acked = _flush_to_sqs(batch)
                    for tag in acked:
                        channel.basic_ack(tag)
                    # Nack messages SQS failed to receive so they retry in RabbitMQ
                    failed_tags = {t for t, _ in batch if t not in acked}
                    for tag in failed_tags:
                        channel.basic_nack(tag, requeue=True)
                    batch = []

            conn.close()
        except Exception as e:
            print(f"Forwarder error: {e} — reconnecting in 5s", flush=True)
            time.sleep(5)


def _shutdown(sig, frame):
    global _running
    print("Shutting down forwarder...", flush=True)
    _running = False


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    run()
