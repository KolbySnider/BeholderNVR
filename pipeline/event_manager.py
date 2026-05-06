"""
EventManager — owns in-memory state for active tracks and emits Kafka events
when tracks open, close, or generate snapshots.

This module is the *producer* of business events. Database writes are
performed by the db_writer consumer, which is the sole owner of Postgres.
"""
import time
import threading
import itertools

from pipeline.producer import (
    publish_event_opened,
    publish_event_closed,
    publish_snapshot,
)

EVENT_TIMEOUT = 5.0
SNAPSHOT_INTERVAL = 3.0


class EventManager:
    def __init__(self):
        self.active_events = {}   # track_id -> event dict
        self.class_keys = {}      # f"{camera}_{class}" -> track_id
        self.lock = threading.Lock()

        # Locally-generated event IDs. We don't depend on the DB to mint them
        # because the DB lives behind Kafka now.
        self._id_counter = itertools.count(int(time.time() * 1000))
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def _next_event_id(self) -> int:
        return next(self._id_counter)

    def process(self, camera_name: str, tracked_objects: list, snapshot_path: str):
        with self.lock:
            now = time.time()

            # Deduplicate — best confidence per class
            best_per_class = {}
            for obj in tracked_objects:
                cls = obj["class"]
                if cls not in best_per_class or obj["confidence"] > best_per_class[cls]["confidence"]:
                    best_per_class[cls] = obj

            for cls, obj in best_per_class.items():
                track_id = obj["track_id"]
                class_key = f"{camera_name}_{cls}"

                if track_id not in self.active_events:
                    # Same class recently seen under a different track id?
                    existing_tid = self.class_keys.get(class_key)
                    if existing_tid and existing_tid in self.active_events:
                        event = self.active_events.pop(existing_tid)
                        event["track_id"] = track_id
                        event["last_seen"] = now
                        self.active_events[track_id] = event
                        self.class_keys[class_key] = track_id

                        if snapshot_path and now - event.get("last_snapshot", 0) >= SNAPSHOT_INTERVAL:
                            publish_snapshot(event["event_id"], snapshot_path, now)
                            event["last_snapshot"] = now
                        continue

                    # Brand new event
                    event_id = self._next_event_id()
                    event = {
                        "event_id": event_id,
                        "track_id": track_id,
                        "camera": camera_name,
                        "class": cls,
                        "first_seen": now,
                        "last_seen": now,
                        "last_snapshot": now,
                    }
                    self.active_events[track_id] = event
                    self.class_keys[class_key] = track_id

                    publish_event_opened(
                        event_id=event_id,
                        camera=camera_name,
                        cls=cls,
                        track_id=track_id,
                        confidence=obj["confidence"],
                        first_seen=now,
                    )
                    if snapshot_path:
                        publish_snapshot(event_id, snapshot_path, now)

                    print(f"[EVENT] New {cls} on {camera_name} (track {track_id}, id {event_id})")

                else:
                    event = self.active_events[track_id]
                    event["last_seen"] = now

                    if snapshot_path and now - event.get("last_snapshot", 0) >= SNAPSHOT_INTERVAL:
                        publish_snapshot(event["event_id"], snapshot_path, now)
                        event["last_snapshot"] = now

    def _cleanup_loop(self):
        while True:
            time.sleep(1)
            now = time.time()
            with self.lock:
                expired = [
                    tid for tid, event in self.active_events.items()
                    if now - event["last_seen"] > EVENT_TIMEOUT
                ]
                for tid in expired:
                    event = self.active_events.pop(tid)
                    dwell = now - event["first_seen"]

                    publish_event_closed(
                        event_id=event["event_id"],
                        dwell_time=dwell,
                        last_seen=event["last_seen"],
                    )

                    class_key = f"{event['camera']}_{event['class']}"
                    if self.class_keys.get(class_key) == tid:
                        self.class_keys.pop(class_key, None)

                    print(f"[EVENT] {event['class']} left {event['camera']} "
                          f"after {dwell:.1f}s (track {tid})")


event_manager = EventManager()