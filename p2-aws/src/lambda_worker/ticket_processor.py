import time
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager


class TicketProcessor:
    """Processes ticket purchase requests with strong consistency via PostgreSQL."""

    def __init__(self, host, port, db, user, password, max_unnumbered, max_seats):
        self.conn_params = dict(host=host, port=port, dbname=db, user=user, password=password,
                                connect_timeout=5)
        self.max_unnumbered = max_unnumbered
        self.max_seats = max_seats
        self._conn = None

    def _get_conn(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.conn_params)
            self._conn.autocommit = False
        return self._conn

    @contextmanager
    def _tx(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            self._conn = None  # force reconnect on next call
            raise

    def process(self, request_id: str, ticket_type: str, seat_number: int = None) -> dict:
        # Simulate payment processing latency (mandatory per spec)
        time.sleep(0.1)

        if ticket_type == "unnumbered":
            return self._buy_unnumbered(request_id)
        elif ticket_type == "numbered":
            return self._buy_numbered(request_id, seat_number)
        else:
            return {"status": "error", "reason": f"unknown ticket_type: {ticket_type}"}

    def _buy_unnumbered(self, request_id: str) -> dict:
        with self._tx() as conn:
            cur = conn.cursor()

            # Idempotency check
            cur.execute("SELECT status FROM tickets WHERE request_id = %s", (request_id,))
            row = cur.fetchone()
            if row:
                return {"status": "duplicate", "original_status": row[0]}

            # Atomic increment with oversell guard
            cur.execute(
                "UPDATE ticket_counter SET sold = sold + 1 WHERE id = 1 AND sold < %s RETURNING sold",
                (self.max_unnumbered,),
            )
            result = cur.fetchone()
            if not result:
                cur.execute(
                    "INSERT INTO tickets(request_id, ticket_type, status) VALUES(%s, %s, %s)",
                    (request_id, "unnumbered", "oversold"),
                )
                return {"status": "oversold"}

            ticket_num = result[0]
            cur.execute(
                "INSERT INTO tickets(request_id, ticket_type, status) VALUES(%s, %s, %s)",
                (request_id, "unnumbered", "success"),
            )
            return {"status": "success", "ticket_number": ticket_num}

    def _buy_numbered(self, request_id: str, seat_number: int) -> dict:
        if seat_number is None or not (1 <= seat_number <= self.max_seats):
            return {"status": "error", "reason": "invalid seat_number"}

        with self._tx() as conn:
            cur = conn.cursor()

            # Idempotency check
            cur.execute("SELECT status FROM tickets WHERE request_id = %s", (request_id,))
            row = cur.fetchone()
            if row:
                return {"status": "duplicate", "original_status": row[0]}

            # Lock the seat row if it exists (prevents concurrent double-sell).
            # The partial unique index idx_seat_unique enforces uniqueness at DB level.
            cur.execute(
                "SELECT 1 FROM tickets "
                "WHERE seat_number = %s AND ticket_type = 'numbered' AND status = 'success' "
                "FOR UPDATE SKIP LOCKED",
                (seat_number,),
            )
            if cur.fetchone():
                # Seat already sold — record the rejection
                cur.execute(
                    "INSERT INTO tickets(request_id, ticket_type, seat_number, status) "
                    "VALUES(%s, 'numbered', %s, 'seat_taken') "
                    "ON CONFLICT(request_id) DO NOTHING",
                    (request_id, seat_number),
                )
                return {"status": "seat_taken", "seat": seat_number}

            cur.execute(
                "INSERT INTO tickets(request_id, ticket_type, seat_number, status) "
                "VALUES(%s, 'numbered', %s, 'success')",
                (request_id, seat_number),
            )
            return {"status": "success", "seat": seat_number}
