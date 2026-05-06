import json
import signal
import sys
from datetime import datetime, timezone

from kafka import KafkaConsumer
from storage.db import init_db, get_connection
from pipeline.producer import (
    BOOTSTRAP_SERVERS,
    TOPIC_EVENT_OPENED,
    TOPIC_EVENT_CLOSED,
    TOPIC_SNAPSHOT,
)

GROUP_ID = "db_writer"


def _ts(epoch: float) -> datetime:
    """Convert an epoch float into a tz-aware datetime."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def handle_event_opened(payload: dict):
    """
    Insert a new event row. Idempotent on event_id thanks to ON CONFLICT.
    """
    sql = """
        INSERT INTO events (id, track_id, camera, class, confidence, first_seen, last_seen)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """
    first_seen = _ts(payload["first_seen"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (
            payload["event_id"],
            payload.get("track_id"),
            payload["camera"],
            payload["class"],
            payload.get("confidence"),
            first_seen,
            first_seen,
        ))
        conn.commit()


def handle_event_closed(payload: dict):
    sql = """
        UPDATE events
           SET last_seen   = %s,
               dwell_time  = %s
         WHERE id = %s
    """
    last_seen = _ts(payload["last_seen"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (last_seen, payload["dwell_time"], payload["event_id"]))
        conn.commit()


def handle_snapshot(payload: dict):
    """
    Insert a snapshot row. Idempotent on (event_id, snapshot) so duplicate
    deliveries don't create duplicate rows.
    """
    sql = """
        INSERT INTO snapshots (event_id, snapshot, captured_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (event_id, snapshot) DO NOTHING
    """
    captured_at = _ts(payload["captured_at"])
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (
            payload["event_id"],
            payload["snapshot_path"],
            captured_at,
        ))
        conn.commit()


HANDLERS = {
    TOPIC_EVENT_OPENED: handle_event_opened,
    TOPIC_EVENT_CLOSED: handle_event_closed,
    TOPIC_SNAPSHOT: handle_snapshot,
}


def run():
    init_db()

    consumer = KafkaConsumer(
        *HANDLERS.keys(),
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    print(f"[DB_WRITER] subscribed to {list(HANDLERS.keys())}")

    def shutdown(*_):
        print("[DB_WRITER] shutting down")
        consumer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for msg in consumer:
        handler = HANDLERS.get(msg.topic)
        if not handler:
            continue
        try:
            handler(msg.value)
        except Exception as e:
            print(f"[DB_WRITER ERROR] {msg.topic}: {e}  payload={msg.value}")


if __name__ == "__main__":
    run()