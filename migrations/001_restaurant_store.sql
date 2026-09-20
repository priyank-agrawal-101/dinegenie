CREATE TABLE IF NOT EXISTS dataset_manifests (
    dataset_version TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL,
    mapping_version TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    canonical_rows INTEGER NOT NULL CHECK (canonical_rows > 0),
    activated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    active_version TEXT,
    previous_version TEXT,
    FOREIGN KEY (active_version) REFERENCES dataset_manifests(dataset_version),
    FOREIGN KEY (previous_version) REFERENCES dataset_manifests(dataset_version)
);

INSERT OR IGNORE INTO dataset_state(singleton, active_version, previous_version)
VALUES (1, NULL, NULL);

CREATE TABLE IF NOT EXISTS restaurants (
    dataset_version TEXT NOT NULL,
    id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_row_ids_json TEXT NOT NULL,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    location_display TEXT NOT NULL,
    location_normalized TEXT NOT NULL,
    listing_zones_json TEXT NOT NULL,
    address TEXT NOT NULL,
    cost_amount INTEGER,
    currency TEXT,
    cost_basis TEXT,
    rating REAL,
    rating_scale REAL,
    votes INTEGER NOT NULL,
    restaurant_types_json TEXT NOT NULL,
    online_order INTEGER NOT NULL,
    book_table INTEGER NOT NULL,
    liked_dishes_json TEXT NOT NULL,
    listing_types_json TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (dataset_version, id),
    FOREIGN KEY (dataset_version) REFERENCES dataset_manifests(dataset_version) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cuisines (
    normalized_name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restaurant_cuisines (
    dataset_version TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    cuisine_normalized TEXT NOT NULL,
    PRIMARY KEY (dataset_version, restaurant_id, cuisine_normalized),
    FOREIGN KEY (dataset_version, restaurant_id)
        REFERENCES restaurants(dataset_version, id) ON DELETE CASCADE,
    FOREIGN KEY (cuisine_normalized) REFERENCES cuisines(normalized_name)
);

CREATE TABLE IF NOT EXISTS verified_tags (
    tag TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS restaurant_verified_tags (
    dataset_version TEXT NOT NULL,
    restaurant_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (dataset_version, restaurant_id, tag),
    FOREIGN KEY (dataset_version, restaurant_id)
        REFERENCES restaurants(dataset_version, id) ON DELETE CASCADE,
    FOREIGN KEY (tag) REFERENCES verified_tags(tag)
);

CREATE INDEX IF NOT EXISTS idx_restaurants_location_rating
ON restaurants(dataset_version, location_normalized, rating);

CREATE INDEX IF NOT EXISTS idx_restaurants_location_cost
ON restaurants(dataset_version, location_normalized, cost_amount);

CREATE INDEX IF NOT EXISTS idx_restaurant_cuisines_lookup
ON restaurant_cuisines(dataset_version, cuisine_normalized, restaurant_id);
