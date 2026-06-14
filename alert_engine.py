"""
Alert engine: turns raw sensor readings and weather forecasts into
human-readable, translated alerts with farmer advice.

Levels (in increasing severity): watch < alert < severe.
"""

from datetime import date, timedelta
from translations import t

LEVEL_RANK = {'safe': 0, 'watch': 1, 'alert': 2, 'severe': 3}


def _day_label(lang, day_offset):
    if day_offset == 0:
        return t(lang, 'day0')
    if day_offset == 1:
        return t(lang, 'day1')
    d = date.today() + timedelta(days=day_offset)
    return d.strftime('%a %d %b')


def evaluate_forecast(days, lang='en'):
    """days: list of dicts from weather.get_forecast (date, tmax, tmin,
    precip_mm, precip_prob, wind_max). Returns list of alert dicts."""
    alerts = []
    for i, day in enumerate(days):
        day_label = _day_label(lang, i)

        # --- Frost ---
        tmin = day['tmin']
        if tmin <= 0:
            level = 'severe'
        elif tmin <= 4:
            level = 'alert'
        elif tmin <= 7:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'frost',
                'level': level,
                'day_offset': i,
                'title': t(lang, 'hazard.frost.title'),
                'message': t(lang, 'hazard.frost.advice', day=day_label, tmin=tmin),
            })

        # --- Heatwave ---
        tmax = day['tmax']
        if tmax >= 42:
            level = 'severe'
        elif tmax >= 39:
            level = 'alert'
        elif tmax >= 36:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'heatwave',
                'level': level,
                'day_offset': i,
                'title': t(lang, 'hazard.heatwave.title'),
                'message': t(lang, 'hazard.heatwave.advice', day=day_label, tmax=tmax),
            })

        # --- Heavy rain ---
        precip = day['precip_mm']
        if precip >= 50:
            level = 'severe'
        elif precip >= 25:
            level = 'alert'
        elif precip >= 12:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'heavy_rain',
                'level': level,
                'day_offset': i,
                'title': t(lang, 'hazard.heavy_rain.title'),
                'message': t(lang, 'hazard.heavy_rain.advice', day=day_label, precip=precip),
            })

        # --- Strong wind / storm ---
        wind = day['wind_max']
        if wind >= 50:
            level = 'severe'
        elif wind >= 35:
            level = 'alert'
        elif wind >= 25:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'storm',
                'level': level,
                'day_offset': i,
                'title': t(lang, 'hazard.storm.title'),
                'message': t(lang, 'hazard.storm.advice', day=day_label, wind=wind),
            })

    return alerts


def evaluate_sensor(reading, farm, lang='en'):
    """reading: sqlite3.Row from sensor_reading. farm: sqlite3.Row from farm
    (provides soil_moisture_min/max thresholds). Returns list of alert dicts."""
    alerts = []
    if reading is None:
        return alerts

    soil = reading['soil_moisture']
    rain = reading['rain_intensity']
    smin = farm['soil_moisture_min']
    smax = farm['soil_moisture_max']

    # --- Soil too dry ---
    if soil is not None:
        if soil <= smin - 5:
            level = 'alert'
        elif soil <= smin:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'dry_soil',
                'level': level,
                'day_offset': 0,
                'title': t(lang, 'hazard.dry_soil.title'),
                'message': t(lang, 'hazard.dry_soil.advice', value=soil),
            })

        # --- Waterlogged soil ---
        if soil >= smax + 5:
            level = 'alert'
        elif soil >= smax:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'waterlogged_soil',
                'level': level,
                'day_offset': 0,
                'title': t(lang, 'hazard.waterlogged_soil.title'),
                'message': t(lang, 'hazard.waterlogged_soil.advice', value=soil),
            })

    # --- Rain sensor: flash flood risk ---
    if rain is not None:
        if rain >= 25:
            level = 'severe'
        elif rain >= 15:
            level = 'alert'
        elif rain >= 8:
            level = 'watch'
        else:
            level = None
        if level:
            alerts.append({
                'hazard': 'flood',
                'level': level,
                'day_offset': 0,
                'title': t(lang, 'hazard.flood.title'),
                'message': t(lang, 'hazard.flood.advice', value=rain),
            })

    return alerts


def overall_risk(alerts, horizon_days=3):
    """Aggregate risk level across alerts within the next `horizon_days`
    (forecast alerts have day_offset; sensor alerts are day_offset 0)."""
    level = 'safe'
    for a in alerts:
        if a['day_offset'] > horizon_days:
            continue
        if LEVEL_RANK[a['level']] > LEVEL_RANK[level]:
            level = a['level']
    return level
