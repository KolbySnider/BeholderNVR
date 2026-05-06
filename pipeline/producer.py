import json
import atexit
from kafka import KafkaProducer

BOOTSTRAP_SERVERS = "localhost:9092"

# Topics
TOPIC_EVENT_OPENED = "events.opened"
TOPIC_EVENT_CLOSED = "events.closed"
TOPIC_SNAPSHOT = "snapshots.captured"
TOPIC_DETECTION_RAW = "detections.raw"

ALL_TOPICS = [
    TOPIC_EVENT_OPENED,
    TOPIC_EVENT_CLOSED,
    TOPIC_SNAPSHOT,
    TOPIC_DETECTION_RAW,
]


_producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
    acks="all",
    linger_ms=10,
    retries=5,
)


def _send(topic: str, key, payload: dict):
    _producer.send(topic, key=key, value=payload)


def publish_event_opened(event_id: int, camera: str, cls: str,
                         track_id: int, confidence: float, first_seen: float):
    _send(TOPIC_EVENT_OPENED, event_id, {
        "event_id": event_id,
        "camera": camera,
        "class": cls,
        "track_id": track_id,
        "confidence": confidence,
        "first_seen": first_seen,
    })


def publish_event_closed(event_id: int, dwell_time: float, last_seen: float):
    _send(TOPIC_EVENT_CLOSED, event_id, {
        "event_id": event_id,
        "dwell_time": dwell_time,
        "last_seen": last_seen,
    })


def publish_snapshot(event_id: int, snapshot_path: str, captured_at: float):
    _send(TOPIC_SNAPSHOT, event_id, {
        "event_id": event_id,
        "snapshot_path": snapshot_path,
        "captured_at": captured_at,
    })


def publish_detection(camera: str, track_id: int, cls: str,
                      confidence: float, bbox: list, ts: float):
    _send(TOPIC_DETECTION_RAW, camera, {
        "camera": camera,
        "track_id": track_id,
        "class": cls,
        "confidence": confidence,
        "bbox": bbox,
        "ts": ts,
    })


def flush():
    _producer.flush()


@atexit.register
def _shutdown():
    try:
        _producer.flush(timeout=5)
        _producer.close(timeout=5)
    except Exception:
        pass