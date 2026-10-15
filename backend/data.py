
import math
import random

from config import INTERVALS_PER_DAY, RNG_SEED


def _base_flow_for_interval(day_index, interval_index):
    """Gallons expected in one 15-minute slot for a 'normal' household."""
    hour = interval_index / 4
    dow = day_index % 7  # 0 = Monday
    is_weekend = dow >= 5
    is_irrigation_day = dow in (1, 5)  # Tuesday / Saturday

    flow = 0.15  # baseline: fridge, toilet cistern refill, minor drips

    if 6 <= hour < 8:  # morning routine
        flow += 2.2 * math.exp(-((hour - 6.8) ** 2) / 0.3)
    if 18 <= hour < 21:  # evening routine
        flow += 1.8 * math.exp(-((hour - 19.2) ** 2) / 0.4)
    if is_irrigation_day and 6 <= hour < 6.5:  # sprinklers
        flow += 6.0
    if is_weekend and 9 <= hour < 17:
        flow += 0.6

    return max(0.05, flow)


def build_dataset(seed=RNG_SEED):
    rng = random.Random(seed)
    readings = []
    anomaly_windows = [
        (12, 2, 5, 3.5),        # day 12, 2am-5am, running toilet
        (27, 1, 4, 5.0),        # day 27, 1am-4am, pipe leak
        (41, 22, 23.75, 9.0),   # day 41, late night, irrigation valve stuck open
    ]

    for day in range(60):
        for interval in range(INTERVALS_PER_DAY):
            hour = interval / 4
            gallons = _base_flow_for_interval(day, interval)
            gallons += rng.gauss(0, 0.12)  # sensor / behavior noise

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
