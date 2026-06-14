import sqlite3
import os
import secrets
from flask import g, current_app

DB_PATH = os.path.join(os.path.dirname(__file__), 'crop_guard.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db


def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        db.executescript(f.read())
    db.commit()
    db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


# ---------------------------------------------------------------------------
# Farm helpers
# ---------------------------------------------------------------------------

def create_farm(name, location_name, lat, lon, language='en', crop_type='general'):
    db = get_db()
    token = secrets.token_hex(8)
    cur = db.execute(
        'INSERT INTO farm (name, location_name, lat, lon, language, crop_type, device_token) '
        'VALUES (?, ?, ?, ?, ?, ?, ?)',
        (name, location_name, lat, lon, language, crop_type, token)
    )
    db.commit()
    return cur.lastrowid, token


def get_farm(farm_id):
    db = get_db()
    return db.execute('SELECT * FROM farm WHERE id = ?', (farm_id,)).fetchone()


def get_farm_by_token(token):
    db = get_db()
    return db.execute('SELECT * FROM farm WHERE device_token = ?', (token,)).fetchone()


def list_farms():
    db = get_db()
    return db.execute('SELECT * FROM farm ORDER BY id').fetchall()


def set_farm_language(farm_id, language):
    db = get_db()
    db.execute('UPDATE farm SET language = ? WHERE id = ?', (language, farm_id))
    db.commit()


# ---------------------------------------------------------------------------
# Sensor readings
# ---------------------------------------------------------------------------

def add_reading(farm_id, device_id, soil_moisture, rain_intensity, air_temperature,
                 air_humidity, timestamp=None):
    db = get_db()
    if timestamp:
        db.execute(
            'INSERT INTO sensor_reading '
            '(farm_id, device_id, timestamp, soil_moisture, rain_intensity, air_temperature, air_humidity) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (farm_id, device_id, timestamp, soil_moisture, rain_intensity, air_temperature, air_humidity)
        )
    else:
        db.execute(
            'INSERT INTO sensor_reading '
            '(farm_id, device_id, soil_moisture, rain_intensity, air_temperature, air_humidity) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (farm_id, device_id, soil_moisture, rain_intensity, air_temperature, air_humidity)
        )
    db.commit()


def latest_reading(farm_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM sensor_reading WHERE farm_id = ? ORDER BY timestamp DESC, id DESC LIMIT 1',
        (farm_id,)
    ).fetchone()


def recent_readings(farm_id, limit=24):
    db = get_db()
    rows = db.execute(
        'SELECT * FROM sensor_reading WHERE farm_id = ? ORDER BY timestamp DESC, id DESC LIMIT ?',
        (farm_id, limit)
    ).fetchall()
    return list(reversed(rows))


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def add_alert(farm_id, source, hazard, level, day_offset, message):
    db = get_db()
    db.execute(
        'INSERT INTO alert (farm_id, source, hazard, level, day_offset, message) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        (farm_id, source, hazard, level, day_offset, message)
    )
    db.commit()


def clear_alerts(farm_id, source=None):
    db = get_db()
    if source:
        db.execute('UPDATE alert SET active = 0 WHERE farm_id = ? AND source = ?', (farm_id, source))
    else:
        db.execute('UPDATE alert SET active = 0 WHERE farm_id = ?', (farm_id,))
    db.commit()


def active_alerts(farm_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM alert WHERE farm_id = ? AND active = 1 ORDER BY '
        "CASE level WHEN 'severe' THEN 0 WHEN 'alert' THEN 1 ELSE 2 END, day_offset",
        (farm_id,)
    ).fetchall()


# ---------------------------------------------------------------------------
# Forecast cache
# ---------------------------------------------------------------------------

def save_forecast_cache(farm_id, payload_json):
    db = get_db()
    db.execute(
        'INSERT INTO forecast_cache (farm_id, fetched_at, payload) VALUES (?, datetime("now"), ?) '
        'ON CONFLICT(farm_id) DO UPDATE SET fetched_at = datetime("now"), payload = excluded.payload',
        (farm_id, payload_json)
    )
    db.commit()


def get_forecast_cache(farm_id):
    db = get_db()
    return db.execute('SELECT * FROM forecast_cache WHERE farm_id = ?', (farm_id,)).fetchone()
