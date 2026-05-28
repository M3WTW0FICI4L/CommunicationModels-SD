"""
Z(t) elastic workload generator.
Produces a time-varying request rate across 5 phases to demonstrate system elasticity.
"""
import time
import uuid
import json
import threading
import math
import random
from dataclasses import dataclass, field
from typing import Callable, List


@dataclass
class Phase:
    name: str
    duration_s: float
    start_rate: float  # req/s at phase start
    end_rate: float    # req/s at phase end (linear interpolation)


# Z(t) workload definition — matches the 5-phase requirement
DEFAULT_WORKLOAD = [
    Phase("low_load",      duration_s=30,  start_rate=5,   end_rate=5),
    Phase("ramp_up",       duration_s=60,  start_rate=5,   end_rate=100),
    Phase("spike",         duration_s=20,  start_rate=250, end_rate=250),
    Phase("sustained_high",duration_s=60,  start_rate=100, end_rate=100),
    Phase("cool_down",     duration_s=30,  start_rate=100, end_rate=5),
]

STRESS_WORKLOAD = [
    Phase("step_5",   duration_s=20, start_rate=5,   end_rate=5),
    Phase("step_20",  duration_s=20, start_rate=20,  end_rate=20),
    Phase("step_50",  duration_s=20, start_rate=50,  end_rate=50),
    Phase("step_100", duration_s=20, start_rate=100, end_rate=100),
    Phase("step_200", duration_s=20, start_rate=200, end_rate=200),
    Phase("step_400", duration_s=20, start_rate=400, end_rate=400),
    Phase("step_800", duration_s=20, start_rate=800, end_rate=800),
]


class WorkloadGenerator:
    """
    Generates ticket purchase requests at Z(t) rates.
    Calls `send_fn(message_dict)` for each request — caller wires this to RabbitMQ.
    """

    def __init__(
        self,
        send_fn: Callable[[dict], None],
        ticket_type: str = "unnumbered",
        max_seats: int = 100_000,
        hotspot: bool = False,
        hotspot_ratio: float = 0.80,
        hotspot_seats_pct: float = 0.05,
        workload: List[Phase] = None,
    ):
        self.send_fn = send_fn
        self.ticket_type = ticket_type
        self.max_seats = max_seats
        self.hotspot = hotspot
        # 80% of requests target 5% of seats
        self.hotspot_seats = int(max_seats * hotspot_seats_pct)
        self.hotspot_ratio = hotspot_ratio
        self.workload = workload or DEFAULT_WORKLOAD
        self._sent = 0
        self._lock = threading.Lock()
        self._events: List[dict] = []

    def _next_seat(self) -> int:
        if not self.hotspot:
            return random.randint(1, self.max_seats)
        if random.random() < self.hotspot_ratio:
            return random.randint(1, self.hotspot_seats)
        return random.randint(self.hotspot_seats + 1, self.max_seats)

    def _make_message(self) -> dict:
        msg = {
            "request_id": str(uuid.uuid4()),
            "ticket_type": self.ticket_type,
            "sent_at": time.time(),
        }
        if self.ticket_type == "numbered":
            msg["seat_number"] = self._next_seat()
        return msg

    def _send_worker(self, msg: dict):
        try:
            self.send_fn(msg)
            with self._lock:
                self._sent += 1
                self._events.append({"t": time.time(), "request_id": msg["request_id"]})
        except Exception as e:
            print(f"[workload] send failed: {e}")

    def run(self) -> List[dict]:
        """Blocking. Returns list of sent event timestamps."""
        print(f"Starting Z(t) workload: {len(self.workload)} phases")
        threads = []
        for phase in self.workload:
            t_phase_start = time.time()
            t_phase_end = t_phase_start + phase.duration_s
            print(f"  Phase [{phase.name}]: {phase.start_rate}→{phase.end_rate} req/s for {phase.duration_s}s")

            while True:
                now = time.time()
                if now >= t_phase_end:
                    break
                progress = (now - t_phase_start) / phase.duration_s
                rate = phase.start_rate + (phase.end_rate - phase.start_rate) * progress
                if rate <= 0:
                    time.sleep(0.01)
                    continue
                interval = 1.0 / rate
                msg = self._make_message()
                t = threading.Thread(target=self._send_worker, args=(msg,), daemon=True)
                t.start()
                threads.append(t)
                time.sleep(interval)

        # Wait for all sends to complete
        for t in threads:
            t.join(timeout=5)

        print(f"Workload complete. Total sent: {self._sent}")
        return self._events
