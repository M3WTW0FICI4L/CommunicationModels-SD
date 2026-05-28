"""
Long-running Lambda worker that consumes tickets from RabbitMQ.

Lifecycle:
- Invoked asynchronously by the scaler (boto3 lambda.invoke InvocationType=Event)
- Connects to RabbitMQ, consumes messages with basic_get in a loop
- For each message: parse JSON, hand off to TicketProcessor, ack
- Exits cleanly on any of:
    * QUIT control message (body == {"action": "quit"})
    * idle timeout (no message for IDLE_TIMEOUT_S consecutive seconds)
    * approaching Lambda timeout (leaves a safety margin)
    * unrecoverable error

This replaces the SQS-event-source-mapping model. The scaler decides how
many Lambdas should be alive at any moment; new ones are invoked when the
backlog grows, QUITs are published when the backlog shrinks.
"""
import json
import os
import time
import uuid
import boto3
import pika
from ticket_processor import TicketProcessor

RABBITMQ_HOST = os.environ["RABBITMQ_HOST"]
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "admin")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "admin123")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "ticket_requests")
IDLE_TIMEOUT_S = float(os.environ.get("IDLE_TIMEOUT_S", "20"))
SAFETY_MARGIN_S = float(os.environ.get("SAFETY_MARGIN_S", "30"))

NAMESPACE = "TicketService"
_cw = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))


def _put_metric(name: str, value: float, unit: str = "Count"):
    try:
        _cw.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{"MetricName": name, "Value": value, "Unit": unit}],
        )
    except Exception:
        pass


def _connect():
    creds = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        credentials=creds,
        heartbeat=60,
        blocked_connection_timeout=30,
        connection_attempts=3,
        retry_delay=2,
    )
    conn = pika.BlockingConnection(params)
    ch = conn.channel()
    ch.queue_declare(queue=RABBITMQ_QUEUE, passive=True)
    ch.basic_qos(prefetch_count=1)
    return conn, ch


def lambda_handler(event, context):
    worker_id = event.get("worker_id") or str(uuid.uuid4())[:8]
    print(f"[{worker_id}] Worker starting")

    processor = TicketProcessor(
        host=os.environ["PG_HOST"],
        port=int(os.environ.get("PG_PORT", 5432)),
        db=os.environ["PG_DB"],
        user=os.environ["PG_USER"],
        password=os.environ["PG_PASS"],
        max_unnumbered=int(os.environ.get("MAX_UNNUMBERED", 100000)),
        max_seats=int(os.environ.get("MAX_SEATS", 100000)),
    )

    conn, ch = _connect()
    _put_metric("WorkerStarted", 1)

    processed = 0
    rejected = 0
    last_msg_at = time.time()
    exit_reason = "unknown"

    try:
        while True:
            # Approaching Lambda timeout — leave a safety margin to finish cleanly
            if context and context.get_remaining_time_in_millis() < SAFETY_MARGIN_S * 1000:
                exit_reason = "timeout_approaching"
                break

            method, _props, body = ch.basic_get(queue=RABBITMQ_QUEUE, auto_ack=False)
            if method is None:
                # Queue empty
                if time.time() - last_msg_at > IDLE_TIMEOUT_S:
                    exit_reason = "idle_timeout"
                    break
                time.sleep(0.05)
                continue

            last_msg_at = time.time()

            try:
                msg = json.loads(body)
            except Exception:
                # Malformed message — ack and skip so it doesn't loop
                ch.basic_ack(method.delivery_tag)
                continue

            if msg.get("action") == "quit":
                ch.basic_ack(method.delivery_tag)
                exit_reason = "quit_message"
                break

            request_id = msg.get("request_id")
            ticket_type = msg.get("ticket_type", "unnumbered")
            seat_number = msg.get("seat_number")

            t0 = time.time()
            try:
                result = processor.process(
                    request_id=request_id,
                    ticket_type=ticket_type,
                    seat_number=seat_number,
                )
                elapsed_ms = (time.time() - t0) * 1000
                ch.basic_ack(method.delivery_tag)

                if result["status"] == "success":
                    processed += 1
                    _put_metric("TicketSold", 1)
                    _put_metric("ProcessingLatencyMs", elapsed_ms, "Milliseconds")
                else:
                    rejected += 1
                    _put_metric("TicketRejected", 1)
            except Exception as e:
                print(f"[{worker_id}] processing error: {e}")
                # Re-queue for another worker to retry
                ch.basic_nack(method.delivery_tag, requeue=True)
                _put_metric("TicketError", 1)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    print(f"[{worker_id}] Exit ({exit_reason}): processed={processed} rejected={rejected}")
    _put_metric("WorkerExited", 1)
    return {
        "worker_id": worker_id,
        "exit_reason": exit_reason,
        "processed": processed,
        "rejected": rejected,
    }
