#!/usr/bin/env python3
"""
Plot benchmark results collected in results/direct/ and results/indirect/.

Produces:
  results/plots/throughput_vs_concurrency_direct.png
  results/plots/throughput_vs_concurrency_indirect.png
  results/plots/direct_vs_indirect_unnumbered.png
  results/plots/direct_vs_indirect_numbered.png
  results/plots/numbered_vs_unnumbered.png
  results/plots/latency_p95_comparison.png

Usage:
    python scripts/plot_results.py
"""

import json
import os
import glob
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RESULTS_DIR_DIRECT   = os.path.join(_REPO_ROOT, "results", "direct")
RESULTS_DIR_INDIRECT = os.path.join(_REPO_ROOT, "results", "indirect")
PLOTS_DIR            = os.path.join(_REPO_ROOT, "results", "plots")

os.makedirs(PLOTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_results(directory: str) -> list[dict]:
    """Load all JSON result files from a directory recursively."""
    out = []
    for path in glob.glob(os.path.join(directory, "**", "*.json"), recursive=True):
        with open(path) as fh:
            data = json.load(fh)
        summary = data.get("summary", data)
        # Extract concurrency and ticket type from filename
        fname = os.path.basename(path)
        # Supports both legacy format: <type>_cX_timestamp.json
        # and new format: results/<arch>/<type>/cX_timestamp.json
        parent_type = os.path.basename(os.path.dirname(path))
        if parent_type in {"unnumbered", "numbered"}:
            summary["_ticket_type"] = parent_type

        m = re.search(r"(?:^|_)?c(\d+)", fname)
        if m:
            summary["_concurrency"] = int(m.group(1))

        if "_ticket_type" not in summary:
            m_type = re.search(r"(unnumbered|numbered)", fname)
            if m_type:
                summary["_ticket_type"] = m_type.group(1)

        summary["_file"] = fname
        out.append(summary)
    return out


def group_by(records: list[dict], key: str) -> dict:
    result = {}
    for r in records:
        k = r.get(key)
        if k not in result:
            result[k] = []
        result[k].append(r)
    return result


# ---------------------------------------------------------------------------
# Plot 1: Throughput vs Concurrency (per architecture, both ticket types)
# ---------------------------------------------------------------------------

def plot_throughput_vs_concurrency(
    results: list[dict],
    arch_label: str = "Direct Architecture",
    filename: str = "throughput_vs_concurrency_direct.png",
) -> None:
    by_type = group_by(results, "_ticket_type")

    fig, ax = plt.subplots(figsize=(8, 5))
    for ticket_type, records in sorted(by_type.items()):
        records.sort(key=lambda r: r.get("_concurrency", 0))
        xs = [r["_concurrency"] for r in records]
        ys = [r.get("throughput_rps", 0) for r in records]
        ax.plot(xs, ys, marker="o", label=ticket_type)

    ax.set_xlabel("Concurrent Clients")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title(f"{arch_label} – Throughput vs Concurrency")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    path = os.path.join(PLOTS_DIR, filename)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Plot 2: Direct vs Indirect comparison (same ticket type & concurrency)
# ---------------------------------------------------------------------------

def plot_direct_vs_indirect(
    direct_results: list[dict],
    indirect_results: list[dict],
    ticket_type: str = "unnumbered",
) -> None:
    def _filter_sort(records, ttype):
        filtered = [r for r in records if r.get("_ticket_type") == ttype]
        filtered.sort(key=lambda r: r.get("_concurrency", 0))
        return filtered

    d_recs = _filter_sort(direct_results, ticket_type)
    i_recs = _filter_sort(indirect_results, ticket_type)

    if not d_recs and not i_recs:
        print("No data for direct vs indirect comparison – skipping plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    if d_recs:
        ax.plot(
            [r["_concurrency"] for r in d_recs],
            [r.get("throughput_rps", 0) for r in d_recs],
            marker="o", label="Direct (REST+NGINX)",
        )
    if i_recs:
        ax.plot(
            [r["_concurrency"] for r in i_recs],
            [r.get("throughput_rps", 0) for r in i_recs],
            marker="s", label="Indirect (RabbitMQ)",
        )

    ax.set_xlabel("Concurrent Clients / Workers")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title(f"Direct vs Indirect – {ticket_type.capitalize()} Tickets")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    path = os.path.join(PLOTS_DIR, f"direct_vs_indirect_{ticket_type}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Plot 3: Numbered vs Unnumbered (direct, same concurrency)
# ---------------------------------------------------------------------------

def plot_numbered_vs_unnumbered(direct_results: list[dict]) -> None:
    by_type = group_by(direct_results, "_ticket_type")
    concurrencies = sorted({r["_concurrency"] for r in direct_results if "_concurrency" in r})

    if not concurrencies:
        print("No concurrency data – skipping numbered vs unnumbered plot.")
        return

    labels = []
    unnumbered_tps = []
    numbered_tps = []

    for c in concurrencies:
        un = [r.get("throughput_rps", 0) for r in by_type.get("unnumbered", [])
              if r.get("_concurrency") == c]
        nb = [r.get("throughput_rps", 0) for r in by_type.get("numbered", [])
              if r.get("_concurrency") == c]
        if un or nb:
            labels.append(str(c))
            unnumbered_tps.append(un[0] if un else 0)
            numbered_tps.append(nb[0] if nb else 0)

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width / 2, unnumbered_tps, width, label="Unnumbered")
    ax.bar(x + width / 2, numbered_tps,   width, label="Numbered")
    ax.set_xlabel("Concurrent Clients")
    ax.set_ylabel("Throughput (req/s)")
    ax.set_title("Unnumbered vs Numbered Tickets – Direct Architecture")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5, axis="y")
    path = os.path.join(PLOTS_DIR, "numbered_vs_unnumbered.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Plot 4: P95 latency comparison across concurrency levels
# ---------------------------------------------------------------------------

def plot_latency_comparison(
    direct_results: list[dict],
    indirect_results: list[dict],
    ticket_type: str = "unnumbered",
) -> None:
    def _filter_sort(records, ttype):
        filtered = [r for r in records if r.get("_ticket_type") == ttype]
        filtered.sort(key=lambda r: r.get("_concurrency", 0))
        return filtered

    d_recs = _filter_sort(direct_results, ticket_type)
    i_recs = _filter_sort(indirect_results, ticket_type)

    if not d_recs and not i_recs:
        print("No latency data – skipping latency comparison plot.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))
    if d_recs:
        ax.plot(
            [r["_concurrency"] for r in d_recs],
            [r.get("p95_response_time_s", 0) * 1000 for r in d_recs],
            marker="o", label="Direct p95",
        )
        ax.plot(
            [r["_concurrency"] for r in d_recs],
            [r.get("mean_response_time_s", 0) * 1000 for r in d_recs],
            marker="o", linestyle="--", label="Direct mean",
        )
    if i_recs:
        ax.plot(
            [r["_concurrency"] for r in i_recs],
            [r.get("p95_response_time_s", 0) * 1000 for r in i_recs],
            marker="s", label="Indirect p95",
        )
        ax.plot(
            [r["_concurrency"] for r in i_recs],
            [r.get("mean_response_time_s", 0) * 1000 for r in i_recs],
            marker="s", linestyle="--", label="Indirect mean",
        )

    ax.set_xlabel("Concurrent Clients")
    ax.set_ylabel("Latency (ms)")
    ax.set_title(f"Latency Comparison – {ticket_type.capitalize()} Tickets")
    ax.legend()
    ax.grid(True, linestyle="--", alpha=0.5)
    path = os.path.join(PLOTS_DIR, f"latency_p95_comparison_{ticket_type}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    direct   = load_results(RESULTS_DIR_DIRECT)
    indirect = load_results(RESULTS_DIR_INDIRECT)

    print(f"Loaded {len(direct)} direct result(s), {len(indirect)} indirect result(s)")

    if direct:
        plot_throughput_vs_concurrency(
            direct,
            arch_label="Direct Architecture",
            filename="throughput_vs_concurrency_direct.png",
        )
        plot_numbered_vs_unnumbered(direct)

    if indirect:
        plot_throughput_vs_concurrency(
            indirect,
            arch_label="Indirect Architecture (RabbitMQ)",
            filename="throughput_vs_concurrency_indirect.png",
        )

    for ttype in ("unnumbered", "numbered"):
        plot_direct_vs_indirect(direct, indirect, ticket_type=ttype)
        plot_latency_comparison(direct, indirect, ticket_type=ttype)

    print("Done.")
