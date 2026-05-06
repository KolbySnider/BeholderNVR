import json
import signal
import sys
from datetime import datetime

from kafka import KafkaConsumer
from pipeline.producer import BOOTSTRAP_SERVERS, TOPIC_EVENT_OPENED

GROUP_ID = "alert_logger"


def run():
    consumer = KafkaConsumer(
        TOPIC_EVENT_OPENED,
        bootstrap_servers=BOOTSTRAP_SERVERS,
        group_id=GROUP_ID,
        value_deserializer=lambda m: json.loads(m.decode("utf-8")),
        auto_offset_reset="latest",
        enable_auto_commit=True,
    )
    print(f"[ALERT] subscribed to {TOPIC_EVENT_OPENED}")

    def shutdown(*_):
        print("[ALERT] shutting down")
        consumer.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    for msg in consumer:
        e = msg.value
        ts = datetime.fromtimestamp(e["first_seen"]).strftime("%H:%M:%S")
        print(f"[ALERT {ts}] {e['class'].upper()} on {e['camera']} "
              f"(conf {e['confidence']:.0%}, event #{e['event_id']})")


if __name__ == "__main__":
    run()