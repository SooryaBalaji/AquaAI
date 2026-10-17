"""Category dictionary served to the browser-side CNN, and the report
generator for the Report Waste tab."""

import random
from datetime import datetime

WASTE_CATEGORIES = {
    "fountain": {"label": "broken sprinkler", "severity": "high", "est_gal_per_min": "15-30"},
    "geyser": {"label": "pipe burst", "severity": "critical", "est_gal_per_min": "50-100"},
    "fire_hydrant": {"label": "open fire hydrant", "severity": "critical", "est_gal_per_min": "500+"},
    "dam": {"label": "flooding / overflow", "severity": "high", "est_gal_per_min": "20-50"},
    "hose": {"label": "unattended hose", "severity": "medium", "est_gal_per_min": "8-12"},
    "pipe": {"label": "pipe leak", "severity": "high", "est_gal_per_min": "10-30"},
}


def build_civic_report(category, lat, lon):
    info = WASTE_CATEGORIES.get(category, {"label": "water waste", "severity": "medium", "est_gal_per_min": "5-20"})
    report_id = f"AQ-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    email_draft = (
        f"Subject: Public Water Waste Report ({info['label']}), Ref {report_id}\n\n"
        f"A resident has reported {info['label']} at coordinates {lat}, {lon}, "
        f"estimated at {info['est_gal_per_min']} gallons/minute. "
        f"Severity: {info['severity']}. Please dispatch for inspection."
    )
    open311_payload = {
        "service_code": "water_waste",
        "lat": lat,
        "long": lon,
        "description": f"{info['label']}, estimated {info['est_gal_per_min']} gal/min",
        "media_url": None,
    }
    return {"report_id": report_id, "category": info, "email_draft": email_draft, "open311_payload": open311_payload}
