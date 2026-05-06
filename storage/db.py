import psycopg2

DB_CONFIG = dict(
    host="localhost",
    port=5432,
    dbname="threats",
    user="admin",
    password="secret",
)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cameras (
            name VARCHAR(50) PRIMARY KEY,
            url TEXT NOT NULL,
            added_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id BIGINT PRIMARY KEY,
            track_id INTEGER,
            camera VARCHAR(50),
            class VARCHAR(50),
            confidence FLOAT,
            first_seen TIMESTAMPTZ,
            last_seen TIMESTAMPTZ,
            dwell_time FLOAT DEFAULT 0,
            anomaly BOOLEAN DEFAULT FALSE
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id SERIAL PRIMARY KEY,
            event_id BIGINT REFERENCES events(id),
            snapshot TEXT,
            captured_at TIMESTAMPTZ,
            UNIQUE (event_id, snapshot)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_events_first_seen ON events(first_seen DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_event_id ON snapshots(event_id)")

    conn.commit()
    cur.close()
    conn.close()
    print("[DB] schema initialized")


def list_cameras():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT name, url FROM cameras ORDER BY added_at ASC")
        return cur.fetchall()


def save_camera(name: str, url: str):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO cameras (name, url) VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET url = EXCLUDED.url
        """, (name, url))
        conn.commit()


def delete_camera(name: str):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM cameras WHERE name = %s", (name,))
        conn.commit()


def delete_event(event_id: int) -> list:
    """Deletes event + snapshot rows. Returns snapshot file paths so caller can unlink them."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT snapshot FROM snapshots WHERE event_id = %s", (event_id,))
        paths = [row[0] for row in cur.fetchall()]
        cur.execute("DELETE FROM snapshots WHERE event_id = %s", (event_id,))
        cur.execute("DELETE FROM events WHERE id = %s", (event_id,))
        conn.commit()
        return paths