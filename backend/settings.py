import storage

DEFAULTS = {
    "leak_alerts": True,
    "budget_alerts": True,
    "weekly_summary": False,
}


class SettingsError(ValueError):
    pass


def get(user_id):
    stored = storage.get_settings(user_id) or {}
    return {key: stored.get(key, default) for key, default in DEFAULTS.items()}


def update(user_id, changes):
    if not isinstance(changes, dict):
        raise SettingsError("Send the settings as a JSON object.")
    unknown = set(changes) - set(DEFAULTS)
    if unknown:
        raise SettingsError("Unknown setting: " + ", ".join(sorted(unknown)))
    for key, value in changes.items():
        if not isinstance(value, bool):
            raise SettingsError(f"{key} must be true or false.")
    merged = {**get(user_id), **changes}
    storage.save_settings(user_id, merged)
    return merged


def delete(user_id):
    storage.delete_settings(user_id)