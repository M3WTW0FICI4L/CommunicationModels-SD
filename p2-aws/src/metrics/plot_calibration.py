#!/usr/bin/env python3
"""Plot throughput vs workers + speedup curve from calibration.json."""
import json
import os
import sys
import matplotlib.pyplot as plt

path = sys.argv[1] if len(sys.argv) > 1 else "results/calibration.json"
out_dir = sys.argv[2] if len(sys.argv) > 2 else "results/plots"
os.makedirs(out_dir, exist_ok=True)

with open(path) as f:
    data = json.load(f)

workers = sorted(int(k) for k in data.keys())
throughputs = [data[str(n)]["throughput"] for n in workers]
t1 = throughputs[0]
speedups = [t / t1 for t in throughputs]
ideal = [n / workers[0] for n in workers]

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

axes[0].plot(workers, throughputs, "o-", color="steelblue", linewidth=2, markersize=8)
axes[0].set_xlabel("Lambda Reserved Concurrency (N)")
axes[0].set_ylabel("Throughput (req/s)")
axes[0].set_title("Throughput vs Workers")
axes[0].set_xscale("log", base=2)
axes[0].grid(True, alpha=0.3, which="both")
for n, t in zip(workers, throughputs):
    axes[0].annotate(f"{t:.1f}", (n, t), textcoords="offset points", xytext=(0, 8), ha="center")

axes[1].plot(workers, speedups, "o-", color="steelblue", linewidth=2, markersize=8, label="Measured")
axes[1].plot(workers, ideal, "--", color="gray", linewidth=1, label="Ideal linear (S=N)")
axes[1].set_xlabel("Lambda Reserved Concurrency (N)")
axes[1].set_ylabel("Speedup S = T_N / T_1")
axes[1].set_title("Speedup Curve")
axes[1].set_xscale("log", base=2)
axes[1].set_yscale("log", base=2)
axes[1].grid(True, alpha=0.3, which="both")
axes[1].legend()

plt.tight_layout()
out = os.path.join(out_dir, "throughput_vs_workers.png")
plt.savefig(out, dpi=150)
print(f"Saved {out}")
