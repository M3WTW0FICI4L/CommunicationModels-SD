import json
import os
import time
import boto3
from ticket_processor import TicketProcessor

_processor = None
_cw = boto3.client("cloudwatch", region_name=os.environ.get("AWS_REGION", "us-east-1"))

NAMESPACE = "TicketService"


def _get_processor():
    global _processor
    if _processor is None:
        _processor = TicketProcessor(
            host=os.environ["PG_HOST"],
            port=int(os.environ.get("PG_PORT", 5432)),
            db=os.environ["PG_DB"],
            user=os.environ["PG_USER"],
            password=os.environ["PG_PASS"],
            max_unnumbered=int(os.environ.get("MAX_UNNUMBERED", 100000)),
            max_seats=int(os.environ.get("MAX_SEATS", 100000)),
        )
    return _processor


def _put_metric(name: str, value: float, unit: str = "Count"):
    try:
        _cw.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[{"MetricName": name, "Value": value, "Unit": unit}],
        )
    except Exception:
        pass


def lambda_handler(event, context):
    processor = _get_processor()
    records = event.get("Records", [])

    successes = 0
    failures = 0

    for record in records:
        body = json.loads(record["body"])
        request_id = body.get("request_id")
        ticket_type = body.get("ticket_type", "unnumbered")
        seat_number = body.get("seat_number")

        t0 = time.time()
        try:
            result = processor.process(
                request_id=request_id,
                ticket_type=ticket_type,
                seat_number=seat_number,
            )
            elapsed_ms = (time.time() - t0) * 1000
            if result["status"] == "success":
                successes += 1
                _put_metric("TicketSold", 1)
                _put_metric("ProcessingLatencyMs", elapsed_ms, "Milliseconds")
            else:
                # idempotent duplicate or oversold — not a failure
                _put_metric("TicketRejected", 1)
        except Exception as e:
            failures += 1
            _put_metric("TicketError", 1)
            # Re-raise so SQS returns the record for retry / DLQ
            raise

    _put_metric("BatchSize", len(records))
    return {"batchItemFailures": []}
