#!/usr/bin/env python3
"""
Generates all required validation plots from analysis JSON files.
Plots:
  1. Throughput vs workers (speedup curve)
  2. Queue backlog vs time
  3. Latency percentiles (p50/p95/p99 bar chart)
  4. Z(t) arrival rate with worker count overlay
"""
import json
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

OUT_DIR = os.environ.get("PLOTS_DIR", "results/plots")


def _load(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def plot_throughput_vs_workers(results_by_workers: dict, out_dir: str):
    """
    results_by_workers: {n_workers: analysis_dict}
    """
    workers = sorted(results_by_workers.keys())
    throughputs = [results_by_workers[n]["throughput"]["throughput_rps"] for n in workers]
    t1 = throughputs[0] if throughputs else 1

    speedups = [t / t1 for t in throughputs]
    ideal = [n / workers[0] for n in workers]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].plot(workers, throughputs, "o-", color="steelblue", linewidth=2, label="Measured")
    axes[0].set_xlabel("Number of Workers (Lambda Concurrency)")
    axes[0].set_ylabel("Throughput (req/s)")
    axes[0].set_title("Throughput vs Workers")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend()

    axes[1].plot(workers, speedups, "o-", color="steelblue", linewidth=2, label="Measured speedup")
    axes[1].plot(workers, ideal, "--", color="gray", linewidth=1, label="Ideal linear speedup")
    axes[1].set_xlabel("Number of Workers")
    axes[1].set_ylabel("Speedup S = T1/Tn")
    axes[1].set_title("Speedup Curve")
    axes[1].grid(True, alpha=0.3)
    axes[1].legend()

    plt.tight_layout()
    path = os.path.join(out_dir, "throughput_vs_workers.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def plot_backlog_vs_time(analysis: dict, out_dir: str, label: str = ""):
    ts = analysis.get("timeseries", {})
    backlog = ts.get("backlog", [])
    workers = ts.get("workers", [])

    if not backlog:
        print("No backlog timeseries data")
        return

    exp_start = analysis["experiment"]["start"]
    bl_t = [(p["t"] - exp_start) for p in backlog]
    bl_v = [p["value"] for p in backlog]

    fig, ax1 = plt.subplots(figsize=(12, 5))
    ax1.fill_between(bl_t, bl_v, alpha=0.3, color="tomato")
    ax1.plot(bl_t, bl_v, color="tomato", linewidth=2, label="Queue Backlog")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Messages in Queue", color="tomato")
    ax1.tick_params(axis="y", labelcolor="tomato")

    if workers:
        ax2 = ax1.twinx()
        wk_t = [(p["t"] - exp_start) for p in workers]
        wk_v = [p["value"] for p in workers]
        ax2.step(wk_t, wk_v, where="post", color="steelblue", linewidth=2, label="Workers")
        ax2.set_ylabel("Worker Count", color="steelblue")
        ax2.tick_params(axis="y", labelcolor="steelblue")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    ax1.set_title(f"Queue Backlog vs Time {label}")
    ax1.grid(True, alpha=0.3)
    plt.tight_layout()
    safe_label = label.replace(" ", "_").replace("/", "_")
    path = os.path.join(out_dir, f"backlog_vs_time{safe_label}.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def plot_latency_percentiles(analyses: dict, out_dir: str):
    """analyses: {label: analysis_dict}"""
    labels = list(analyses.keys())
    p50 = [analyses[l]["latency"].get("p50_ms", 0) for l in labels]
    p95 = [analyses[l]["latency"].get("p95_ms", 0) for l in labels]
    p99 = [analyses[l]["latency"].get("p99_ms", 0) for l in labels]

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 2), 5))
    ax.bar(x - width, p50, width, label="p50", color="steelblue")
    ax.bar(x, p95, width, label="p95", color="orange")
    ax.bar(x + width, p99, width, label="p99", color="tomato")
    ax.axhline(100, linestyle="--", color="gray", linewidth=1, label="100ms (payment delay)")

    ax.set_xlabel("Experiment")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("End-to-End Latency Percentiles")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    path = os.path.join(out_dir, "latency_percentiles.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"Saved: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_files", nargs="+", help="Path(s) to analysis JSON files")
    parser.add_argument("--out", default=OUT_DIR)
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    analyses = {}
    for path in args.analysis_files:
        label = os.path.splitext(os.path.basename(path))[0]
        analyses[label] = _load(path)

    # Backlog for each experiment
    for label, data in analyses.items():
        plot_backlog_vs_time(data, args.out, label=f" ({label})")

    # Latency comparison across experiments
    plot_latency_percentiles(analyses, args.out)

    # Throughput vs workers (if files are named worker_N_...)
    by_workers = {}
    for label, data in analyses.items():
        parts = label.split("_")
        for i, p in enumerate(parts):
            if p == "w" and i + 1 < len(parts):
                try:
                    by_workers[int(parts[i + 1])] = data
                except ValueError:
                    pass
    if len(by_workers) >= 2:
        plot_throughput_vs_workers(by_workers, args.out)


if __name__ == "__main__":
    main()
