import json
import random
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, jsonify, flash

import db
import weather
import alert_engine
from translations import t, LANGUAGES

app = Flask(__name__)
app.secret_key = 'crop-guard-demo-secret'
db.init_app(app)

CROP_TYPES = ['general', 'rice', 'ragi', 'maize', 'sugarcane', 'cotton', 'vegetables', 'groundnut']

FORECAST_CACHE_MINUTES = 30

# Needle endpoint (x, y) on the 200x120 risk-gauge SVG for each risk level
GAUGE_NEEDLE_POS = {
    'safe': (35.33, 73.21),
    'watch': (73.21, 35.33),
    'alert': (126.79, 35.33),
    'severe': (164.67, 73.21),
}


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

@app.context_processor
def inject_helpers():
    return {
        't': t,
        'LANGUAGES': LANGUAGES,
        'CROP_TYPES': CROP_TYPES,
        'needle_positions': GAUGE_NEEDLE_POS,
    }


# ---------------------------------------------------------------------------
# Core data helpers
# ---------------------------------------------------------------------------

def get_forecast_for_farm(farm):
    """Return (days, source) using the forecast cache when fresh."""
    cache = db.get_forecast_cache(farm['id'])
    if cache:
        fetched_at = datetime.strptime(cache['fetched_at'], '%Y-%m-%d %H:%M:%S')
        age = datetime.utcnow() - fetched_at
        if age < timedelta(minutes=FORECAST_CACHE_MINUTES):
            payload = json.loads(cache['payload'])
            return payload['days'], payload['source']

    days, source = weather.get_forecast(farm['lat'], farm['lon'], demo_seed=farm['id'])
    db.save_forecast_cache(farm['id'], json.dumps({'days': days, 'source': source}))
    return days, source


def build_dashboard_data(farm):
    lang = farm['language']
    days, source = get_forecast_for_farm(farm)
    reading = db.latest_reading(farm['id'])
    history = db.recent_readings(farm['id'], limit=24)

    forecast_alerts = alert_engine.evaluate_forecast(days, lang=lang)
    sensor_alerts = alert_engine.evaluate_sensor(reading, farm, lang=lang)

    all_alerts = forecast_alerts + sensor_alerts
    risk = alert_engine.overall_risk(all_alerts)

    # Persist a snapshot of current alerts for record-keeping
    db.clear_alerts(farm['id'])
    for a in all_alerts:
        db.add_alert(farm['id'], 'forecast' if a['hazard'] not in
                      ('dry_soil', 'waterlogged_soil', 'flood') else 'sensor',
                      a['hazard'], a['level'], a['day_offset'], a['message'])

    # Add translated day labels to forecast for the template
    days_display = []
    for i, d in enumerate(days):
        days_display.append({
            **d,
            'label': alert_engine._day_label(lang, i),
        })

    return {
        'farm': farm,
        'lang': lang,
        'reading': reading,
        'history': history,
        'forecast': days_display,
        'forecast_source': source,
        'alerts': sorted(all_alerts, key=lambda a: (alert_engine.LEVEL_RANK[a['level']] * -1, a['day_offset'])),
        'risk': risk,
        'needle': GAUGE_NEEDLE_POS[risk],
    }


# ---------------------------------------------------------------------------
# Routes: farm management
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    farms = db.list_farms()
    return render_template('index.html', farms=farms)


@app.route('/add_farm', methods=['GET', 'POST'])
def add_farm():
    if request.method == 'POST':
        name = request.form['name'].strip()
        location_name = request.form['location_name'].strip()
        lat = float(request.form['lat'])
        lon = float(request.form['lon'])
        language = request.form.get('language', 'en')
        crop_type = request.form.get('crop_type', 'general')

        farm_id, token = db.create_farm(name, location_name, lat, lon, language, crop_type)
        flash(f'Farm "{name}" created. Device token: {token}')
        return redirect(url_for('dashboard', farm_id=farm_id))

    return render_template('add_farm.html')


@app.route('/farm/<int:farm_id>')
def dashboard(farm_id):
    farm = db.get_farm(farm_id)
    if farm is None:
        return 'Farm not found', 404
    data = build_dashboard_data(farm)
    return render_template('dashboard.html', **data)


@app.route('/farm/<int:farm_id>/language', methods=['POST'])
def set_language(farm_id):
    lang = request.form.get('language', 'en')
    if lang in LANGUAGES:
        db.set_farm_language(farm_id, lang)
    return redirect(url_for('dashboard', farm_id=farm_id))


@app.route('/farm/<int:farm_id>/load_demo', methods=['POST'])
def load_demo(farm_id):
    farm = db.get_farm(farm_id)
    if farm is None:
        return 'Farm not found', 404
    seed_sensor_history(farm)
    return redirect(url_for('dashboard', farm_id=farm_id))


# ---------------------------------------------------------------------------
# API: hardware devices push readings here
# ---------------------------------------------------------------------------

@app.route('/api/sensor-data', methods=['POST'])
def api_sensor_data():
    data = request.get_json(silent=True) or request.form
    token = data.get('device_token')
    farm = db.get_farm_by_token(token) if token else None
    if farm is None:
        return jsonify({'error': 'invalid device_token'}), 401

    def _f(key):
        val = data.get(key)
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return None

    db.add_reading(
        farm_id=farm['id'],
        device_id=data.get('device_id', 'unknown'),
        soil_moisture=_f('soil_moisture'),
        rain_intensity=_f('rain_intensity'),
        air_temperature=_f('air_temperature'),
        air_humidity=_f('air_humidity'),
    )
    return jsonify({'status': 'ok'})


@app.route('/api/farm/<int:farm_id>/status')
def api_farm_status(farm_id):
    farm = db.get_farm(farm_id)
    if farm is None:
        return jsonify({'error': 'not found'}), 404
    data = build_dashboard_data(farm)
    reading = data['reading']

    return jsonify({
        'risk': data['risk'],
        'risk_label': t(data['lang'], f"risk.{data['risk']}"),
        'reading': dict(reading) if reading else None,
        'alerts': [
            {
                'hazard': a['hazard'],
                'level': a['level'],
                'title': a['title'],
                'message': a['message'],
                'day_offset': a['day_offset'],
            }
            for a in data['alerts']
        ],
        'forecast': data['forecast'],
        'forecast_source': data['forecast_source'],
    })


# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

def seed_sensor_history(farm, hours=24):
    """Populate `hours` of hourly synthetic sensor readings ending now,
    crafted so the latest reading trips a couple of alerts for the demo."""
    rnd = random.Random(farm['id'] * 7919)
    now = datetime.utcnow()

    base_soil = rnd.uniform(35, 55)
    base_temp = 34 - abs(farm['lat']) * 0.35

    for h in range(hours, 0, -1):
        ts = now - timedelta(hours=h)
        hour_of_day = ts.hour
        # diurnal temperature swing
        temp = base_temp + 6 * (0.5 - abs(hour_of_day - 14) / 24) + rnd.uniform(-1, 1)
        humidity = max(20, min(95, 70 - (temp - base_temp) * 2 + rnd.uniform(-5, 5)))
        soil = max(5, min(95, base_soil + rnd.uniform(-3, 3)))
        rain = max(0, rnd.gauss(0.5, 1.5))

        db.add_reading(
            farm_id=farm['id'],
            device_id='demo-sim',
            soil_moisture=round(soil, 1),
            rain_intensity=round(max(0, rain), 1),
            air_temperature=round(temp, 1),
            air_humidity=round(humidity, 1),
            timestamp=ts.strftime('%Y-%m-%d %H:%M:%S'),
        )

    # Final "now" reading: nudge values so the dashboard shows at least one
    # live sensor alert (dry soil) alongside the forecast alerts.
    db.add_reading(
        farm_id=farm['id'],
        device_id='demo-sim',
        soil_moisture=round(max(5, base_soil - 22), 1),
        rain_intensity=round(max(0, rnd.gauss(0.5, 1.0)), 1),
        air_temperature=round(base_temp + rnd.uniform(2, 4), 1),
        air_humidity=round(rnd.uniform(40, 60), 1),
    )


@app.route('/seed_demo')
def seed_demo():
    """Create a handful of demo farms across India with sample sensor
    history, for first-run/demo purposes."""
    if db.list_farms():
        flash('Demo data already exists.')
        return redirect(url_for('index'))

    demo_farms = [
        ('Hosalli Paddy Farm', 'Mandya, Karnataka', 12.5242, 76.8958, 'kn', 'rice'),
        ('Belagavi Sugarcane Estate', 'Belagavi, Karnataka', 15.8497, 74.4977, 'kn', 'sugarcane'),
        ('Vidarbha Cotton Fields', 'Nagpur, Maharashtra', 21.1458, 79.0882, 'hi', 'cotton'),
        ('Green Valley Vegetable Farm', 'Coimbatore, Tamil Nadu', 11.0168, 76.9558, 'en', 'vegetables'),
    ]

    for name, loc, lat, lon, lang, crop in demo_farms:
        farm_id, _token = db.create_farm(name, loc, lat, lon, lang, crop)
        farm = db.get_farm(farm_id)
        seed_sensor_history(farm)

    flash('Demo farms created with sample sensor data.')
    return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@app.cli.command('init-db')
def init_db_command():
    db.init_db()
    print('Initialized the database.')


if __name__ == '__main__':
    db.init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
