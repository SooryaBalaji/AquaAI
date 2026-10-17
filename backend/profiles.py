"""
Household profiles.

Every profile has an owner_id. The seeded demo profile has owner_id=None,
meaning it's public and visible to everyone, including signed-out
visitors. Any profile a user creates through create_profile() is private
to that user; list_profiles() only ever returns the demo profile plus the
requesting user's own.

Profile records are persisted through storage.py, so they survive a
server restart. The trained Isolation Forest per profile is deliberately
kept in-memory only, in _cache: retraining after a restart costs a
fraction of a second, so there's no reason to persist it.
"""

import random
import uuid

import storage
from anomaly_model import train_anomaly_model
from config import LATITUDE, LONGITUDE, TIER_1_LIMIT_GAL
from data import build_dataset

DEFAULT_PROFILE_ID = "demo"

MAX_NAME_LENGTH = 60
MAX_PLACE_LENGTH = 80
MIN_HOUSEHOLD_SIZE = 1
MAX_HOUSEHOLD_SIZE = 20
MIN_TIER1_LIMIT_GAL = 500
MAX_TIER1_LIMIT_GAL = 100_000
MAX_PROFILES_PER_USER = 5

_cache = {}  # profile_id -> {"readings": [...], "model": ..., "anomalies": [...]}


class ValidationError(Exception):
    """Raised for bad profile input. Message is safe to show the user"""


def _new_profile(profile_id, owner_id, name, lat, lon, household_size, tier1_limit_gal, seed, place=None):
    return {
        "id": profile_id,
        "owner_id": owner_id,
        "name": name,
        "lat": lat,
        "lon": lon,
        "household_size": household_size,
        "tier1_limit_gal": tier1_limit_gal,
        "seed": seed,
        "place": place,
    }


def init():
    """Call once at startup: connects storage and seeds the demo profile
    if it isn't already there (for example, on a fresh SQLite file)."""
    storage.init_storage()
    if storage.get_profile(DEFAULT_PROFILE_ID) is None:
        storage.save_profile(
            _new_profile(DEFAULT_PROFILE_ID, None, "Demo household", LATITUDE, LONGITUDE, 4, TIER_1_LIMIT_GAL, seed=42)
        )


def storage_backend():
    return storage.backend_name()


def list_profiles(owner_id=None):
    return storage.list_profiles(owner_id)


def get_profile(profile_id):
    return storage.get_profile(profile_id)


def can_view(profile, user_id):
    """A profile is visible if it's public (owner_id None) or owned by
    this user."""
    return profile is not None and (profile.get("owner_id") is None or profile.get("owner_id") == user_id)


def _validate(name, lat, lon, household_size, tier1_limit_gal):
    name = (name or "").strip()
    if not name:
        raise ValidationError("Household name is required.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Household name must be {MAX_NAME_LENGTH} characters or fewer.")

    try:
        household_size = int(household_size)
    except (TypeError, ValueError):
        raise ValidationError("Household size must be a number.")
    if not (MIN_HOUSEHOLD_SIZE <= household_size <= MAX_HOUSEHOLD_SIZE):
        raise ValidationError(f"Household size must be between {MIN_HOUSEHOLD_SIZE} and {MAX_HOUSEHOLD_SIZE}.")

    try:
        tier1_limit_gal = float(tier1_limit_gal)
    except (TypeError, ValueError):
        raise ValidationError("Tier 1 limit must be a number.")
    if not (MIN_TIER1_LIMIT_GAL <= tier1_limit_gal <= MAX_TIER1_LIMIT_GAL):
        raise ValidationError(f"Tier 1 limit must be between {MIN_TIER1_LIMIT_GAL} and {MAX_TIER1_LIMIT_GAL} gallons.")

    try:
        lat = float(lat)
        lon = float(lon)
    except (TypeError, ValueError):
        raise ValidationError("Location coordinates must be numbers.")
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        raise ValidationError("Location coordinates are out of range.")

    return name, lat, lon, household_size, tier1_limit_gal


def _clean_place(place):
    place = (place or "").strip() if isinstance(place, str) else ""
    if len(place) > MAX_PLACE_LENGTH:
        raise ValidationError(f"Place name must be {MAX_PLACE_LENGTH} characters or fewer.")
    return place or None


def create_profile(owner_id, name, lat, lon, household_size, tier1_limit_gal, place=None):
    if not owner_id:
        raise ValidationError("You must be signed in to create a household.")

    name, lat, lon, household_size, tier1_limit_gal = _validate(name, lat, lon, household_size, tier1_limit_gal)

    owned = [p for p in storage.list_profiles(owner_id) if p.get("owner_id") == owner_id]
    if len(owned) >= MAX_PROFILES_PER_USER:
        raise ValidationError(f"You can have up to {MAX_PROFILES_PER_USER} households. Delete one to add another.")

    profile_id = uuid.uuid4().hex[:8]
    profile = _new_profile(
        profile_id, owner_id, name, lat, lon, household_size, tier1_limit_gal,
        seed=random.randint(1, 1_000_000),
        place=_clean_place(place),
    )
    storage.save_profile(profile)
    return profile


EDITABLE = ("name", "lat", "lon", "household_size", "tier1_limit_gal", "place")


def update_profile(profile_id, owner_id, changes):
    """Edits a household the caller owns. Returns the updated profile, or
    None if it doesn't exist or isn't theirs (the demo household is nobody's)."""
    profile = storage.get_profile(profile_id)
    if not profile or not owner_id or profile.get("owner_id") != owner_id:
        return None
    if not isinstance(changes, dict) or not set(changes) & set(EDITABLE):
        raise ValidationError("Nothing to change.")

    merged = {**profile, **{k: changes[k] for k in EDITABLE if k in changes}}
    name, lat, lon, size, tier = _validate(
        merged["name"], merged["lat"], merged["lon"], merged["household_size"], merged["tier1_limit_gal"]
    )
    updated = {**profile, "name": name, "lat": lat, "lon": lon, "household_size": size,
               "tier1_limit_gal": tier, "place": _clean_place(merged.get("place"))}
    storage.save_profile(updated)
    if size != profile["household_size"]:
        _cache.pop(profile_id, None)  # usage data is built from the household size
    return updated


def is_simulated(profile):
    """Only the shared demo household (no owner) runs on generated readings."""
    return profile.get("owner_id") is None


def delete_profile(profile_id, owner_id):
    profile = storage.get_profile(profile_id)
    if not profile or profile.get("owner_id") != owner_id or profile.get("owner_id") is None:
        return False
    storage.delete_profile_row(profile_id)
    storage.delete_usage(profile_id)
    _cache.pop(profile_id, None)
    return True


def delete_all_for_owner(owner_id):
    if not owner_id:
        return 0
    owned = [p for p in storage.list_profiles(owner_id) if p.get("owner_id") == owner_id]
    for p in owned:
        storage.delete_profile_row(p["id"])
        storage.delete_usage(p["id"])
        _cache.pop(p["id"], None)
    return len(owned)


def get_household_data(profile_id):
    """Returns the cached {readings, model, anomalies} for a profile,
    training the Isolation Forest on first access after each restart."""
    if profile_id in _cache:
        return _cache[profile_id]

    profile = get_profile(profile_id)
    if not profile:
        return None

    readings = build_dataset(seed=profile["seed"], household_size=profile["household_size"])
    model, anomalies = train_anomaly_model(readings)
    entry = {"readings": readings, "model": model, "anomalies": anomalies}
    _cache[profile_id] = entry
    return entry