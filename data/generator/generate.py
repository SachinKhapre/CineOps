"""Synthetic MediaDoc event generator.

Generates users, content, and viewing_events for N days of "normal" traffic
plus one injected incident day (Incident A: Android + Maharashtra + 1080p/4K
buffering degradation, 19:00-22:00). Ground truth lives in
scenarios/incident_a.json so the agent's findings can be scored later.

Usage:
    python generate.py --scale small
"""
import argparse
import csv
import random
import uuid
from datetime import datetime, timedelta

import clickhouse_connect

SCALE_PRESETS = {
    "small": {"users": 2_000, "sessions_per_user_per_day": 3},
    "medium": {"users": 20_000, "sessions_per_user_per_day": 4},
    "large": {"users": 150_000, "sessions_per_user_per_day": 5},
}

NUM_CONTENT = 200
NUM_DAYS = 8  # last day is the incident day
INCIDENT_HOUR_START = 19
INCIDENT_HOUR_END = 22

REGIONS = [("Maharashtra", "IN"), ("Telangana", "IN"), ("Karnataka", "IN"),
           ("England", "UK"), ("California", "US")]
GENRES = ["Drama", "Comedy", "Thriller", "Documentary"]
LANGUAGES = ["en", "hi", "te"]
DEVICE_TYPES = ["Android", "iOS", "Web"]
QUALITIES = ["720p", "1080p", "4K"]
AGE_BANDS = ["13-17", "18-24", "25-34", "35-50", "50+"]
TIERS = ["basic", "standard", "premium"]

BASE_COMPLETION_PROB = 0.75
BASE_BUFFER_PROB = 0.021
INCIDENT_BUFFER_PROB = 0.108
INCIDENT_COMPLETION_PROB = 0.45


def is_incident_slot(day_index, device_type, region, quality, hour):
    return (
        day_index == NUM_DAYS - 1
        and device_type == "Android"
        and region == "Maharashtra"
        and quality in ("1080p", "4K")
        and INCIDENT_HOUR_START <= hour < INCIDENT_HOUR_END
    )


def gen_content(rng):
    rows = []
    for i in range(NUM_CONTENT):
        rows.append((
            f"c{i:04d}",
            f"Title {i:04d}",
            rng.choice(GENRES),
            rng.choice(LANGUAGES),
            "movie" if rng.random() < 0.6 else "series",
        ))
    return rows


def gen_users(rng, n):
    rows = []
    for i in range(n):
        region, country = rng.choice(REGIONS)
        rows.append((
            f"u{i:06d}",
            region,
            country,
            rng.choice(AGE_BANDS),
            rng.choice(TIERS),
        ))
    return rows


def gen_events_for_session(rng, user, content, day_index, anchor_date):
    user_id, region, _country, _age, _tier = user
    content_id = content[0]
    device_type = rng.choice(DEVICE_TYPES)
    platform = "app" if device_type != "Web" else "web"
    quality = rng.choice(QUALITIES)
    network = rng.choice(["wifi", "cellular"])
    duration = rng.choice([1500, 2400, 3000, 5400])

    hour = rng.randint(6, 23)
    minute = rng.randint(0, 59)
    ts = anchor_date + timedelta(days=day_index, hours=hour, minutes=minute)

    incident = is_incident_slot(day_index, device_type, region, quality, hour)
    buffer_prob = INCIDENT_BUFFER_PROB if incident else BASE_BUFFER_PROB
    completion_prob = INCIDENT_COMPLETION_PROB if incident else BASE_COMPLETION_PROB

    session_id = str(uuid.uuid4())
    events = []
    t = ts
    events.append((t, "play", 0))
    t += timedelta(seconds=2)

    if rng.random() < buffer_prob:
        buf_ms = rng.randint(3000, 15000)
        events.append((t, "buffer_start", 0, buf_ms))
        t += timedelta(milliseconds=buf_ms)
        events.append((t, "buffer_end", 0, 0))

    completed = rng.random() < completion_prob
    if completed:
        events.append((t, "complete", duration))
    else:
        pos = rng.randint(1, duration - 1)
        events.append((t, "skip" if rng.random() < 0.5 else "exit", pos))

    rows = []
    for e in events:
        ts_, event_type, pos = e[0], e[1], e[2]
        buf_ms = e[3] if len(e) > 3 else 0
        rows.append((
            str(uuid.uuid4()), ts_, user_id, content_id, session_id,
            event_type, pos, duration, device_type, platform, quality,
            region, _country, network, "none", buf_ms,
        ))
    return rows


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def load_to_clickhouse(host, port, users_rows, content_rows, events_path, batch_size=50_000):
    client = clickhouse_connect.get_client(host=host, port=port)
    client.insert("mediadoc.users", users_rows,
                  column_names=["user_id", "region", "country", "age_band", "subscription_tier"])
    client.insert("mediadoc.content", content_rows,
                  column_names=["content_id", "title", "genre", "language", "content_type"])

    columns = ["event_id", "event_timestamp", "user_id", "content_id", "session_id",
               "event_type", "watch_position_seconds", "video_duration_seconds",
               "device_type", "platform", "quality", "region", "country",
               "network_type", "error_code", "buffer_duration_ms"]
    batch = []
    with open(events_path, encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            batch.append(row)
            if len(batch) >= batch_size:
                client.insert("mediadoc.viewing_events", batch, column_names=columns)
                batch = []
        if batch:
            client.insert("mediadoc.viewing_events", batch, column_names=columns)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=SCALE_PRESETS.keys(), default="small")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--dry-run", action="store_true", help="write CSVs only, skip ClickHouse load")
    args = parser.parse_args()

    preset = SCALE_PRESETS[args.scale]
    rng = random.Random(args.seed)
    anchor_date = datetime(2026, 9, 1)

    content_rows = gen_content(rng)
    users_rows = gen_users(rng, preset["users"])

    events_path = f"{args.out_dir}/viewing_events.csv"
    header = ["event_id", "event_timestamp", "user_id", "content_id", "session_id",
              "event_type", "watch_position_seconds", "video_duration_seconds",
              "device_type", "platform", "quality", "region", "country",
              "network_type", "error_code", "buffer_duration_ms"]
    with open(events_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for day_index in range(NUM_DAYS):
            for user in users_rows:
                content = rng.choice(content_rows)
                for _ in range(preset["sessions_per_user_per_day"]):
                    rows = gen_events_for_session(rng, user, content, day_index, anchor_date)
                    w.writerows(rows)

    write_csv(f"{args.out_dir}/users.csv",
              ["user_id", "region", "country", "age_band", "subscription_tier"], users_rows)
    write_csv(f"{args.out_dir}/content.csv",
              ["content_id", "title", "genre", "language", "content_type"], content_rows)

    if args.dry_run:
        print(f"Wrote CSVs to {args.out_dir} (dry run, no ClickHouse load)")
    else:
        load_to_clickhouse(args.host, args.port, users_rows, content_rows, events_path)
        print(f"Loaded {preset['users']} users, {NUM_CONTENT} content, "
              f"incident day = {(anchor_date + timedelta(days=NUM_DAYS - 1)).date()}")


if __name__ == "__main__":
    main()
