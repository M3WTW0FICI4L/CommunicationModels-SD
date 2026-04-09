#!/usr/bin/env python3
"""
Generate a HIGH-CONTENTION numbered benchmark file.

80 % of requests target 5 % of the seat pool (seats 1–1000 out of 20 000).
The remaining 20 % are spread uniformly across all 20 000 seats.

Usage:
    python scripts/generate_contention_benchmark.py \
        --output benchmarks/benchmark_numbered_contention.txt \
        --total  60000
"""

import argparse
import random


TOTAL_SEATS = 20_000
HOT_FRACTION = 0.05     # 5 % of seats are "hot"
HOT_TRAFFIC = 0.80      # 80 % of requests go to hot seats


def generate(total_requests: int, output_path: str, seed: int = 42) -> None:
    rng = random.Random(seed)

    hot_pool_size = int(TOTAL_SEATS * HOT_FRACTION)          # 1 000
    hot_seats = list(range(1, hot_pool_size + 1))             # 1–1000
    cold_seats = list(range(hot_pool_size + 1, TOTAL_SEATS + 1))  # 1001–20000

    n_hot = int(total_requests * HOT_TRAFFIC)
    n_cold = total_requests - n_hot

    lines = []

    for i in range(1, n_hot + 1):
        seat = rng.choice(hot_seats)
        client_id = f"user{i:05d}"
        request_id = f"hot{i:06d}"
        lines.append(f"BUY {client_id} {seat} {request_id}")

    for i in range(1, n_cold + 1):
        seat = rng.choice(cold_seats)
        client_id = f"user{n_hot + i:05d}"
        request_id = f"cold{i:06d}"
        lines.append(f"BUY {client_id} {seat} {request_id}")

    rng.shuffle(lines)

    with open(output_path, "w") as fh:
        fh.write("# Concert Ticket Benchmark – Numbered Seats – HIGH CONTENTION\n")
        fh.write(f"# Total requests: {total_requests}\n")
        fh.write(f"# Hot seats: 1–{hot_pool_size} ({HOT_TRAFFIC*100:.0f}% of traffic)\n")
        fh.write(f"# Cold seats: {hot_pool_size+1}–{TOTAL_SEATS}\n")
        fh.write("# Format: BUY <client_id> <seat_id> <request_id>\n")
        for line in lines:
            fh.write(line + "\n")

    print(f"Generated {total_requests} requests → {output_path}")
    print(f"  Hot requests : {n_hot} ({n_hot/total_requests*100:.1f}%)")
    print(f"  Cold requests: {n_cold} ({n_cold/total_requests*100:.1f}%)")
    print(f"  Hot seat pool: seats 1–{hot_pool_size}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="High-contention benchmark generator")
    parser.add_argument(
        "--output",
        default="benchmarks/benchmark_numbered_contention.txt",
    )
    parser.add_argument("--total", type=int, default=60_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    generate(args.total, args.output, seed=args.seed)
