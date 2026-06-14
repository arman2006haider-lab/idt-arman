"""
Crop Guard - Sensor Simulator
------------------------------
Sends randomized sensor readings to a running Crop Guard server's
/api/sensor-data endpoint, simulating an ESP32/Raspberry Pi sensor node.
Useful for demos and testing without physical hardware.

Usage:
    python hardware/sensor_simulator.py --token <device_token> [--url http://localhost:5000] [--once]
"""

import argparse
import random
import time

import requests


def random_reading():
    return {
        'soil_moisture': round(random.uniform(15, 70), 1),
        'rain_intensity': round(max(0, random.gauss(2, 4)), 1),
        'air_temperature': round(random.uniform(20, 38), 1),
        'air_humidity': round(random.uniform(35, 90), 1),
    }


def main():
    parser = argparse.ArgumentParser(description='Crop Guard sensor simulator')
    parser.add_argument('--token', required=True, help='Farm device token')
    parser.add_argument('--url', default='http://localhost:5000', help='Crop Guard server base URL')
    parser.add_argument('--device-id', default='sim-node-1', help='Device identifier')
    parser.add_argument('--interval', type=int, default=30, help='Seconds between readings')
    parser.add_argument('--once', action='store_true', help='Send a single reading and exit')
    args = parser.parse_args()

    endpoint = args.url.rstrip('/') + '/api/sensor-data'

    while True:
        payload = random_reading()
        payload['device_token'] = args.token
        payload['device_id'] = args.device_id

        try:
            resp = requests.post(endpoint, json=payload, timeout=5)
            print('Sent:', payload, '-> status', resp.status_code, resp.text)
        except Exception as exc:
            print('Error sending reading:', exc)

        if args.once:
            break
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
