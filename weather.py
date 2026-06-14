"""
Weather forecast helper.

Tries to fetch a real 7-day forecast from the free Open-Meteo API
(https://open-meteo.com - no API key required). If the network call
fails (e.g. offline environment, demo mode), it falls back to a
deterministic synthetic forecast so the rest of the app still has
realistic data to work with.
"""

import json
import random
from datetime import date, timedelta

import requests

OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast'


def fetch_live_forecast(lat, lon, timeout=5):
    """Fetch a 7-day daily forecast from Open-Meteo. Returns list of day dicts
    or None if the request fails."""
    params = {
        'latitude': lat,
        'longitude': lon,
        'daily': ','.join([
            'temperature_2m_max',
            'temperature_2m_min',
            'precipitation_sum',
            'precipitation_probability_max',
            'windspeed_10m_max',
        ]),
        'timezone': 'auto',
        'forecast_days': 7,
    }
    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        daily = data['daily']
        days = []
        for i, d in enumerate(daily['time']):
            days.append({
                'date': d,
                'tmax': daily['temperature_2m_max'][i],
                'tmin': daily['temperature_2m_min'][i],
                'precip_mm': daily['precipitation_sum'][i],
                'precip_prob': daily['precipitation_probability_max'][i],
                'wind_max': daily['windspeed_10m_max'][i],
            })
        return days
    except Exception:
        return None


def synthetic_forecast(lat, lon, seed=None):
    """Generate a realistic-looking 7 day forecast offline.

    Deterministic per (lat, lon) so the same farm always sees the same demo
    data, but the pattern is crafted to include at least one of each hazard
    type (frost, heatwave, heavy rain, storm) so the alert engine and UI have
    something interesting to show in a demo.
    """
    rnd = random.Random(seed if seed is not None else round(lat * 1000) + round(lon * 1000))
    today = date.today()

    # Base climate guess from latitude: closer to equator -> hotter.
    base_temp = 34 - abs(lat) * 0.35

    days = []
    for i in range(7):
        d = today + timedelta(days=i)
        tmax = base_temp + rnd.uniform(-3, 3)
        tmin = tmax - rnd.uniform(8, 14)
        precip_mm = max(0, rnd.gauss(2, 4))
        precip_prob = min(100, max(0, precip_mm * 12 + rnd.uniform(-10, 15)))
        wind_max = max(5, rnd.gauss(15, 8))

        days.append({
            'date': d.isoformat(),
            'tmax': round(tmax, 1),
            'tmin': round(tmin, 1),
            'precip_mm': round(precip_mm, 1),
            'precip_prob': round(precip_prob, 1),
            'wind_max': round(wind_max, 1),
        })

    # --- Bake in a few notable hazard days so the demo is presentable ---
    # Day 1: heavy rain / flood risk
    days[1]['precip_mm'] = 62.0
    days[1]['precip_prob'] = 95.0
    days[1]['wind_max'] = round(max(days[1]['wind_max'], 28), 1)

    # Day 3: cold night -> frost risk
    days[3]['tmin'] = 2.5
    days[3]['tmax'] = round(min(days[3]['tmax'], 18), 1)

    # Day 5: heatwave
    days[5]['tmax'] = 42.5
    days[5]['tmin'] = round(max(days[5]['tmin'], 26), 1)

    return days


def get_forecast(lat, lon, demo_seed=None):
    """Return a 7-day forecast, preferring live data and falling back to a
    synthetic forecast if offline."""
    live = fetch_live_forecast(lat, lon)
    if live:
        return live, 'live'
    return synthetic_forecast(lat, lon, seed=demo_seed), 'demo'


def forecast_to_json(days):
    return json.dumps(days)


def forecast_from_json(payload):
    return json.loads(payload)
