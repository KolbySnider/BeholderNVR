"""
Launcher: brings up Kafka + Postgres in Docker, then starts the
db_writer and alert_logger consumers and the dashboard.
"""
import subprocess
import time
import sys


def run(cmd, name):
    print(f"[START] {name}")
    return subprocess.Popen(cmd, shell=True)


if __name__ == "__main__":
    print("[START] Docker containers...")
    subprocess.run("docker compose up -d", shell=True)
    print("[WAIT] Giving Kafka 10 seconds to initialize...")
    time.sleep(10)

    db_writer = run(
        f"{sys.executable} -m pipeline.db_writer",
        "DB Writer (Kafka -> Postgres)",
    )
    alert_logger = run(
        f"{sys.executable} -m pipeline.alert_logger",
        "Alert Logger (Kafka -> stdout)",
    )
    time.sleep(2)

    dashboard = run(
        f"{sys.executable} dashboard/app.py",
        "Dashboard",
    )

    print("\n[INFO] All services started")
    print("[INFO] Press CTRL+C to stop everything\n")

    try:
        dashboard.wait()
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down...")
        for p in (dashboard, alert_logger, db_writer):
            p.terminate()
        for p in (dashboard, alert_logger, db_writer):
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        subprocess.run("docker compose down", shell=True)
        print("[STOP] All services stopped")

