# 🌾 Crop Guard — Multilingual Weather & Sensor Alert System

A full-stack Flask app that helps farmers protect their crops from
unseasonal weather. It combines a **7-day weather forecast** with **live
sensor readings** (soil moisture, rain intensity, air temperature/humidity)
from low-cost hardware, and turns both into a single **crop risk gauge**
with plain-language alerts and farming advice — in **English, Kannada
(ಕನ್ನಡ) or Hindi (हिन्दी)**, chosen per farm.

## Features

- **Multi-farm dashboard** — register any number of farms with their own
  location, crop type, and alert language.
- **Risk gauge** — a Safe → Watch → Alert → Severe dial combining forecast
  hazards (frost, heatwave, heavy rain, storm) and live sensor hazards (dry
  soil, waterlogging, flash-flood-level rain).
- **Live sensor dashboard** — soil moisture, rain intensity, air temperature
  and humidity, updated automatically (polls every 15s).
- **Translated alerts with advice** — e.g. "Temperatures may drop to 2.5°C
  tomorrow. Irrigate lightly in the evening and cover seedlings."
- **Hardware integration API** — a simple `POST /api/sensor-data` endpoint
  any ESP32/Raspberry Pi/Arduino device can call using a per-farm device
  token.
- **Works offline** — if the weather API is unreachable, a deterministic
  synthetic forecast (with realistic hazard days) is used so the dashboard
  is always demo-able.
- **One-click demo data** — `/seed_demo` creates four sample farms across
  India (Karnataka, Maharashtra, Tamil Nadu) with 24h of sensor history.

## Project structure

```
crop_guard/
  app.py                # Flask routes & dashboard logic
  db.py                 # SQLite data access layer
  schema.sql            # Database schema
  weather.py            # Open-Meteo forecast + offline fallback
  alert_engine.py        # Turns sensor/forecast data into alerts
  translations.py        # English / Kannada / Hindi UI strings
  templates/              # Jinja2 templates
  static/css/style.css   # App styling
  static/js/dashboard.js # Live polling + alarm sound
  hardware/
    esp32_sensor_node.ino # Example ESP32 firmware
    sensor_simulator.py    # Python script to simulate a sensor device
  requirements.txt
```

## Running locally

```bash
cd crop_guard
pip install -r requirements.txt --break-system-packages   # if needed
python3 -c "import db; db.init_db()"                      # create the DB
python3 app.py                                              # http://localhost:5000
```

Then open `http://localhost:5000/seed_demo` once to populate four demo
farms with sample sensor history and forecast-driven alerts, or click
**"Load demo farms"** on the home page.

## Connecting real hardware

1. Register a farm via **Add Farm**. The dashboard shows a **device token**.
2. Flash `hardware/esp32_sensor_node.ino` onto an ESP32 with:
   - a soil moisture sensor (analog),
   - a rain-drop sensor (analog),
   - a DHT22 temperature/humidity sensor,

   filling in your Wi-Fi credentials, server URL, and the device token.
3. The device POSTs JSON like this every few minutes:

   ```json
   {
     "device_token": "abcd1234...",
     "device_id": "esp32-field-node-1",
     "soil_moisture": 42.5,
     "rain_intensity": 1.2,
     "air_temperature": 29.1,
     "air_humidity": 60.0
   }
   ```

No hardware yet? Run the simulator instead:

```bash
python3 hardware/sensor_simulator.py --token <device_token> --interval 30
```

## How risk levels are calculated

`alert_engine.py` evaluates each forecast day and the latest sensor reading
against thresholds (tunable per farm via `soil_moisture_min/max` and the
hard-coded weather thresholds), producing alerts at **watch / alert /
severe** levels:

| Hazard | Source | Trigger (approx.) |
|---|---|---|
| Frost | forecast | min temp ≤ 7°C (watch) … ≤ 0°C (severe) |
| Heatwave | forecast | max temp ≥ 36°C (watch) … ≥ 42°C (severe) |
| Heavy rain | forecast | rainfall ≥ 12mm (watch) … ≥ 50mm (severe) |
| Storm / strong wind | forecast | wind ≥ 25 km/h (watch) … ≥ 50 km/h (severe) |
| Dry soil | sensor | soil moisture at/below configured minimum |
| Waterlogging | sensor | soil moisture at/above configured maximum |
| Flash flood | sensor | rain sensor ≥ 8 mm/hr (watch) … ≥ 25 mm/hr (severe) |

The overall **crop risk gauge** shows the highest-severity alert due within
the next 3 days.

## Notes / next steps for production

- Swap the dev server for a production WSGI server (gunicorn) and consider
  PostgreSQL for multi-farm scale.
- For farmers without smartphones, hook alerts into SMS/IVR (e.g. Twilio,
  or a local telecom gateway) — the alert/translation logic is already
  separated so this is mostly a new "delivery channel" module.
- Tune the soil-moisture and weather thresholds per crop type
  (`farm.crop_type` is already stored and ready to use for this).
