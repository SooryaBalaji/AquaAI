import re
from functools import lru_cache

import requests

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

TIMEOUT = 5


class GeocodeError(Exception):
    pass


def _zip_lookup(code):
    r = requests.get(f"https://api.zippopotam.us/us/{code}", timeout=TIMEOUT)
    if r.status_code == 404:
        return []
    r.raise_for_status()
    out = []
    for p in r.json().get("places", [])[:1]:
        out.append({
            "label": f"{p['place name']}, {p['state']} {code}",
            "lat": float(p["latitude"]),
            "lon": float(p["longitude"]),
        })
    return out


def _name_lookup(query):
    name, _, region = (part.strip() for part in query.partition(","))
    if not name:
        return []
    r = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": name, "count": 20, "language": "en", "countryCode": "US", "format": "json"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    wanted = STATES.get(region.upper(), region).lower()
    out = []
    for p in r.json().get("results") or []:
        state = p.get("admin1") or ""
        if wanted and not state.lower().startswith(wanted):
            continue
        out.append({
            "label": f"{p['name']}, {state}" if state else p["name"],
            "lat": float(p["latitude"]),
            "lon": float(p["longitude"]),
        })
    seen, unique = set(), []
    for item in out:
        if item["label"] not in seen:
            seen.add(item["label"])
            unique.append(item)
    return unique[:8]


@lru_cache(maxsize=512)
def _search_cached(query):
    try:
        if re.fullmatch(r"\d{5}", query):
            return tuple(map(lambda d: tuple(d.items()), _zip_lookup(query)))
        return tuple(map(lambda d: tuple(d.items()), _name_lookup(query)))
    except (requests.RequestException, KeyError, ValueError) as e:
        raise GeocodeError(str(e))


def search(query):
    query = (query or "").strip()
    if len(query) < 2 or len(query) > 60:
        return []
    return [dict(items) for items in _search_cached(query.lower())]
