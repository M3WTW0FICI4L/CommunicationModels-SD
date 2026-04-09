"""Allow `python -m src.indirect.worker` to start a worker."""
import argparse
from .worker import IndirectWorker, WorkerPool

parser = argparse.ArgumentParser()
parser.add_argument("--worker-id", default="worker-0")
parser.add_argument("--workers", type=int, default=1)
args = parser.parse_args()

if args.workers == 1:
    w = IndirectWorker(worker_id=args.worker_id)
    w.start()
else:
    import time
    pool = WorkerPool(initial_workers=args.workers)
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pool.stop_all()
