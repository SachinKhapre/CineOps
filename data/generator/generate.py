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
import json
import os
import random
import uuid
from datetime import datetime, timedelta, timezone

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
BASE_SKIP_SHARE = 0.5  # of non-completions, skip vs exit

# Incident A (§17): playback degradation, narrow to device+region+quality+hours.
INCIDENT_A_BUFFER_PROB = 0.108
INCIDENT_A_COMPLETION_PROB = 0.45

# Incident C (§17): one title's engagement collapses -- skip rate +70%,
# completion -35% -- while buffering stays perfectly normal. That normal
# buffering is the discriminator: an agent that blames infrastructure here is
# wrong in exactly the way §40 counts as a false positive.
INCIDENT_C_CONTENT_ID = "c0042"
INCIDENT_C_COMPLETION_PROB = 0.49  # 0.75 * 0.65
INCIDENT_C_SKIP_SHARE = 0.42  # lifts skip rate 0.125 -> ~0.21 given more non-completions


def is_incident_a_slot(day_index, device_type, region, quality, hour):
    return (
        day_index == NUM_DAYS - 1
        and device_type == "Android"
        and region == "Maharashtra"
        and quality in ("1080p", "4K")
        and INCIDENT_HOUR_START <= hour < INCIDENT_HOUR_END
    )


def is_incident_c_slot(day_index, content_id):
    return day_index == NUM_DAYS - 1 and content_id == INCIDENT_C_CONTENT_ID


def session_probabilities(incident, day_index, device_type, region, quality, hour, content_id):
    """(buffer_prob, completion_prob, skip_share) for one session."""
    if incident == "a" and is_incident_a_slot(day_index, device_type, region, quality, hour):
        return INCIDENT_A_BUFFER_PROB, INCIDENT_A_COMPLETION_PROB, BASE_SKIP_SHARE
    if incident == "c" and is_incident_c_slot(day_index, content_id):
        return BASE_BUFFER_PROB, INCIDENT_C_COMPLETION_PROB, INCIDENT_C_SKIP_SHARE
    return BASE_BUFFER_PROB, BASE_COMPLETION_PROB, BASE_SKIP_SHARE


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


def gen_events_for_session(rng, user, content, day_index, anchor_date, incident):
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

    buffer_prob, completion_prob, skip_share = session_probabilities(
        incident, day_index, device_type, region, quality, hour, content_id
    )

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
        events.append((t, "skip" if rng.random() < skip_share else "exit", pos))

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


def load_to_clickhouse(host, port, user, password, users_rows, content_rows, events_path, batch_size=50_000):
    client = clickhouse_connect.get_client(host=host, port=port, username=user, password=password)
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
            row[1] = datetime.fromisoformat(row[1]).replace(tzinfo=timezone.utc)
            row[6] = int(row[6])
            row[7] = int(row[7])
            row[15] = int(row[15])
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
    parser.add_argument("--user", default="default")
    parser.add_argument("--password", default=os.environ.get("CLICKHOUSE_ADMIN_PASSWORD", "mediadoc_admin_pw"))
    parser.add_argument("--out-dir", default=".")
    parser.add_argument("--incident", choices=["a", "c"], default="a",
                        help="which §17 incident to inject: a=playback degradation, c=content anomaly")
    parser.add_argument("--dry-run", action="store_true", help="write CSVs only, skip ClickHouse load")
    args = parser.parse_args()

    preset = SCALE_PRESETS[args.scale]
    rng = random.Random(args.seed)
    anchor_date = datetime(2026, 9, 1)

    # The eval harness scores the agent against this scenario file, so drift
    # between the generated incident day and the recorded one would look like
    # the agent picked the wrong day. Fail here instead, where it's obvious.
    incident_day = (anchor_date + timedelta(days=NUM_DAYS - 1)).date().isoformat()
    scenario_path = os.path.join(os.path.dirname(__file__), "scenarios", f"incident_{args.incident}.json")
    recorded_day = json.load(open(scenario_path))["incident_day"]
    assert incident_day == recorded_day, f"generated incident day {incident_day} != {scenario_path} {recorded_day}"

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
                    rows = gen_events_for_session(rng, user, content, day_index, anchor_date, args.incident)
                    w.writerows(rows)

    write_csv(f"{args.out_dir}/users.csv",
              ["user_id", "region", "country", "age_band", "subscription_tier"], users_rows)
    write_csv(f"{args.out_dir}/content.csv",
              ["content_id", "title", "genre", "language", "content_type"], content_rows)

    if args.dry_run:
        print(f"Wrote CSVs to {args.out_dir} (dry run, no ClickHouse load)")
    else:
        load_to_clickhouse(args.host, args.port, args.user, args.password, users_rows, content_rows, events_path)
        print(f"Loaded {preset['users']} users, {NUM_CONTENT} content, "
              f"incident {args.incident.upper()} on {incident_day}")


if __name__ == "__main__":
    main()
