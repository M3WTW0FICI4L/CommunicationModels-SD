#!/usr/bin/env python3
"""
Collects completed-transaction timestamps from PostgreSQL and computes:
  - Throughput (completed / total_time)
  - Latency distribution (p50, p95, p99)
  - Queue backlog over time (from CloudWatch)

Usage:
  python analyzer.py --start <epoch> --end <epoch> --output results/analysis.json
"""
import argparse
import json
import os
import time
import boto3
import psycopg2
import numpy as np
from datetime import datetime, timezone

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
PG_HOST = os.environ["PG_HOST"]
PG_PORT = int(os.environ.get("PG_PORT", 5432))
PG_DB = os.environ.get("PG_DB", "tickets")
PG_USER = os.environ.get("PG_USER", "ticket_user")
PG_PASS = os.environ.get("PG_PASS", "ticket_pass")

cw = boto3.client("cloudwatch", region_name=AWS_REGION)


def _pg_conn():
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DB,
                            user=PG_USER, password=PG_PASS)


def fetch_completed_transactions(start_epoch: float, end_epoch: float) -> list:
    """Returns rows processed between start and end (server-side timestamps)."""
    conn = _pg_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT request_id, status, processed_at FROM tickets "
        "WHERE processed_at BETWEEN %s AND %s ORDER BY processed_at",
        (datetime.fromtimestamp(start_epoch, tz=timezone.utc),
         datetime.fromtimestamp(end_epoch, tz=timezone.utc)),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def compute_throughput(rows: list, start_epoch: float, end_epoch: float) -> dict:
    total_time = end_epoch - start_epoch
    successful = [r for r in rows if r[1] == "success"]
    return {
        "total_completed": len(rows),
        "total_successful": len(successful),
        "total_time_s": total_time,
        "throughput_rps": len(rows) / total_time if total_time > 0 else 0,
        "success_throughput_rps": len(successful) / total_time if total_time > 0 else 0,
    }


def compute_latency_percentiles(client_events: list, db_rows: list) -> dict:
    """
    Computes end-to-end latency by matching client send_at with server processed_at.
    client_events: [{request_id, t (send epoch)}]
    db_rows: [(request_id, status, processed_at)]
    """
    send_map = {e["request_id"]: e["t"] for e in client_events}
    latencies_ms = []
    for req_id, status, processed_at in db_rows:
        if req_id in send_map and processed_at:
            proc_epoch = processed_at.timestamp()
            latency_ms = (proc_epoch - send_map[req_id]) * 1000
            if latency_ms > 0:
                latencies_ms.append(latency_ms)

    if not latencies_ms:
        return {}
    arr = np.array(latencies_ms)
    return {
        "count": len(arr),
        "p50_ms": float(np.percentile(arr, 50)),
        "p95_ms": float(np.percentile(arr, 95)),
        "p99_ms": float(np.percentile(arr, 99)),
        "mean_ms": float(np.mean(arr)),
        "max_ms": float(np.max(arr)),
        "min_ms": float(np.min(arr)),
    }


def fetch_cloudwatch_metric(metric_name: str, start_epoch: float, end_epoch: float,
                             stat: str = "Maximum", period: int = 10) -> list:
    resp = cw.get_metric_statistics(
        Namespace="TicketService",
        MetricName=metric_name,
        StartTime=datetime.fromtimestamp(start_epoch, tz=timezone.utc),
        EndTime=datetime.fromtimestamp(end_epoch, tz=timezone.utc),
        Period=period,
        Statistics=[stat],
    )
    points = sorted(resp["Datapoints"], key=lambda x: x["Timestamp"])
    return [{"t": p["Timestamp"].timestamp(), "value": p[stat]} for p in points]


def analyze(start_epoch: float, end_epoch: float,
            client_events: list = None, output_path: str = None) -> dict:
    print("Fetching completed transactions from PostgreSQL...")
    rows = fetch_completed_transactions(start_epoch, end_epoch)

    throughput = compute_throughput(rows, start_epoch, end_epoch)
    latency = compute_latency_percentiles(client_events or [], rows)

    print("Fetching CloudWatch metrics...")
    backlog_ts = fetch_cloudwatch_metric("QueueBacklog", start_epoch, end_epoch)
    arrival_ts = fetch_cloudwatch_metric("ArrivalRate", start_epoch, end_epoch, stat="Average")
    workers_ts = fetch_cloudwatch_metric("TargetWorkers", start_epoch, end_epoch, stat="Maximum")

    result = {
        "experiment": {"start": start_epoch, "end": end_epoch},
        "throughput": throughput,
        "latency": latency,
        "timeseries": {
            "backlog": backlog_ts,
            "arrival_rate": arrival_ts,
            "workers": workers_ts,
        },
    }

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"Analysis saved to {output_path}")

    _print_summary(throughput, latency)
    return result


def _print_summary(t: dict, l: dict):
    print("\n===== RESULTS =====")
    print(f"Total completed: {t['total_completed']}")
    print(f"Successful:      {t['total_successful']}")
    print(f"Total time:      {t['total_time_s']:.1f}s")
    print(f"Throughput:      {t['throughput_rps']:.1f} req/s")
    if l:
        print(f"Latency p50:     {l['p50_ms']:.0f} ms")
        print(f"Latency p95:     {l['p95_ms']:.0f} ms")
        print(f"Latency p99:     {l['p99_ms']:.0f} ms")
    print("===================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--events", help="Path to client events JSON")
    parser.add_argument("--output", default="results/analysis.json")
    args = parser.parse_args()

    events = []
    if args.events:
        with open(args.events) as f:
            data = json.load(f)
            events = data.get("events", [])

    analyze(args.start, args.end, events, args.output)
