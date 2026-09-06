CREATE DATABASE IF NOT EXISTS mediadoc;

CREATE TABLE IF NOT EXISTS mediadoc.content
(
    content_id   String,
    title        String,
    genre        LowCardinality(String),
    language     LowCardinality(String),
    content_type LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY content_id;

CREATE TABLE IF NOT EXISTS mediadoc.users
(
    user_id            String,
    region             LowCardinality(String),
    country            LowCardinality(String),
    age_band           LowCardinality(String),
    subscription_tier  LowCardinality(String)
)
ENGINE = MergeTree
ORDER BY user_id;

CREATE TABLE IF NOT EXISTS mediadoc.viewing_events
(
    event_id               String,
    event_timestamp        DateTime,
    user_id                String,
    content_id             String,
    session_id             String,
    event_type             LowCardinality(String),
    watch_position_seconds UInt32,
    video_duration_seconds UInt32,
    device_type            LowCardinality(String),
    platform               LowCardinality(String),
    quality                LowCardinality(String),
    region                 LowCardinality(String),
    country                LowCardinality(String),
    network_type           LowCardinality(String),
    error_code             LowCardinality(String),
    buffer_duration_ms     UInt32
)
ENGINE = MergeTree
PARTITION BY toDate(event_timestamp)
ORDER BY (event_timestamp, content_id);
