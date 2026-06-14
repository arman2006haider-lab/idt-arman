-- Crop Guard / Field Watch database schema

CREATE TABLE IF NOT EXISTS farm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location_name TEXT,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    language TEXT DEFAULT 'en',
    crop_type TEXT DEFAULT 'general',
    device_token TEXT UNIQUE,
    soil_moisture_min REAL DEFAULT 20,
    soil_moisture_max REAL DEFAULT 85,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sensor_reading (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    device_id TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    soil_moisture REAL,
    rain_intensity REAL,
    air_temperature REAL,
    air_humidity REAL,
    FOREIGN KEY(farm_id) REFERENCES farm(id)
);
CREATE INDEX IF NOT EXISTS idx_reading_farm_ts ON sensor_reading(farm_id, timestamp);

CREATE TABLE IF NOT EXISTS alert (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_id INTEGER NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    source TEXT,           -- 'sensor' or 'forecast'
    hazard TEXT,           -- e.g. 'frost', 'heatwave', 'heavy_rain', 'flood', 'dry_soil', 'storm'
    level TEXT,            -- 'watch', 'alert', 'severe'
    day_offset INTEGER DEFAULT 0,  -- 0 = now/today, 1..6 = forecast day
    message TEXT,
    active INTEGER DEFAULT 1,
    FOREIGN KEY(farm_id) REFERENCES farm(id)
);
CREATE INDEX IF NOT EXISTS idx_alert_farm ON alert(farm_id, active);

CREATE TABLE IF NOT EXISTS forecast_cache (
    farm_id INTEGER PRIMARY KEY,
    fetched_at TEXT,
    payload TEXT,          -- JSON blob of forecast days
    FOREIGN KEY(farm_id) REFERENCES farm(id)
);
