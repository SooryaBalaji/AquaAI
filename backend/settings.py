import storage

DEFAULTS = {
    "leak_alerts": True,
    "budget_alerts": True,
    "weekly_summary": False,
    "via_email": True,
    "via_sms": False,
}


class SettingsError(ValueError):
    pass


def get(user_id, has_phone=True):
    merged = {**DEFAULTS, **(storage.get_settings(user_id) or {})}
    if not has_phone:
        merged["via_sms"] = False
    return merged


def update(user_id, changes, has_phone):
    if not isinstance(changes, dict):
        raise SettingsError("Send the settings as a JSON object.")
    unknown = set(changes) - set(DEFAULTS)
    if unknown:
        raise SettingsError("Unknown setting: " + ", ".join(sorted(unknown)))
    for key, value in changes.items():
        if not isinstance(value, bool):
            raise SettingsError(f"{key} must be true or false.")
    merged = {**get(user_id, has_phone), **changes}
    if merged["via_sms"] and not has_phone:
        raise SettingsError("Link a phone number before turning on text alerts.")
    storage.save_settings(user_id, merged)
    return merged


def delete(user_id):
    storage.delete_settings(user_id)