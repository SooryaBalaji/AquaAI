"""
Simulates 60 days of 15-minute household water-meter readings.

Clearly labeled as simulated: a real deployment would pull these from a
utility's smart-meter API (e.g. WaterSmart), which needs a partnership this
project doesn't have. Each profile gets its own seed, so different
households in the app do not share identical usage or leak history.
"""

import math
import random

from config import INTERVALS_PER_DAY


def _base_flow_for_interval(day_index, interval_index, size_factor):
    """Gallons expected in one 15-minute slot for a 'normal' household of
    this size. size_factor is household_size / 4, the reference size the
    base curve was tuned for."""
    hour = interval_index / 4
    dow = day_index % 7  # 0 = Monday
    is_weekend = dow >= 5
    is_irrigation_day = dow in (1, 5)  # Tuesday / Saturday

    flow = 0.15 * size_factor  # baseline: fridge, toilet cistern refill, minor drips

    if 6 <= hour < 8:  # morning routine
        flow += 2.2 * size_factor * math.exp(-((hour - 6.8) ** 2) / 0.3)
    if 18 <= hour < 21:  # evening routine
        flow += 1.8 * size_factor * math.exp(-((hour - 19.2) ** 2) / 0.4)
    if is_irrigation_day and 6 <= hour < 6.5:  # sprinklers (lot size, not household size)
        flow += 6.0
    if is_weekend and 9 <= hour < 17:
        flow += 0.6 * size_factor

    return max(0.05, flow)


def _random_anomaly_windows(rng):
    """Plants two or three realistic problems (a running toilet, a pipe
    leak, a stuck irrigation valve) on random days, so the Isolation
    Forest in anomaly_model.py has something genuine to find."""
    kinds = [
        (2, 5, 3.5),      # overnight, running toilet
        (1, 4, 5.0),      # overnight, pipe leak
        (22, 23.75, 9.0),  # late evening, irrigation valve stuck open
    ]
    count = rng.randint(2, 3)
    chosen_days = rng.sample(range(5, 58), count)
    windows = []
    for day in chosen_days:
        start_h, end_h, extra = rng.choice(kinds)
        windows.append((day, start_h, end_h, extra))
    return windows


def build_dataset(seed, household_size=4):
    rng = random.Random(seed)
    size_factor = max(0.4, household_size / 4)
    readings = []
    anomaly_windows = _random_anomaly_windows(rng)

    for day in range(60):
        for interval in range(INTERVALS_PER_DAY):
            hour = interval / 4
            gallons = _base_flow_for_interval(day, interval, size_factor)
            gallons += rng.gauss(0, 0.12 * size_factor)  # sensor / behavior noise

            injected = False
            for (a_day, start_h, end_h, extra) in anomaly_windows:
                if day == a_day and start_h <= hour < end_h:
                    gallons += extra + rng.gauss(0, 0.4)
                    injected = True

            readings.append({
                "day": day,
                "interval": interval,
                "hour": hour,
                "dow": day % 7,
                "gallons": round(max(0, gallons), 3),
                "injected_anomaly": injected,
            })
    return readings
