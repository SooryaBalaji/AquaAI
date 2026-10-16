import pytest

import profiles


def test_demo_profile_is_public():
    demo = profiles.get_profile(profiles.DEFAULT_PROFILE_ID)
    assert demo is not None
    assert demo["owner_id"] is None
    assert profiles.can_view(demo, user_id=None)
    assert profiles.can_view(demo, user_id="anyone")


def test_create_requires_owner():
    with pytest.raises(profiles.ValidationError):
        profiles.create_profile(owner_id=None, name="No owner", lat=1, lon=1, household_size=4, tier1_limit_gal=4000)


def test_create_rejects_empty_name():
    with pytest.raises(profiles.ValidationError):
        profiles.create_profile(owner_id="u1", name="  ", lat=1, lon=1, household_size=4, tier1_limit_gal=4000)


@pytest.mark.parametrize("size", [0, -1, 21, 1000])
def test_create_rejects_household_size_out_of_range(size):
    with pytest.raises(profiles.ValidationError):
        profiles.create_profile(owner_id="u1", name="Test", lat=1, lon=1, household_size=size, tier1_limit_gal=4000)


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_create_rejects_bad_coordinates(lat, lon):
    with pytest.raises(profiles.ValidationError):
        profiles.create_profile(owner_id="u1", name="Test", lat=lat, lon=lon, household_size=4, tier1_limit_gal=4000)


def test_owner_can_view_and_delete_own_profile():
    p = profiles.create_profile(owner_id="owner-1", name="Mine", lat=1, lon=1, household_size=4, tier1_limit_gal=4000)
    assert profiles.can_view(p, "owner-1")
    assert not profiles.can_view(p, "someone-else")
    assert profiles.delete_profile(p["id"], "owner-1") is True


def test_non_owner_cannot_delete():
    p = profiles.create_profile(owner_id="owner-2", name="Mine", lat=1, lon=1, household_size=4, tier1_limit_gal=4000)
    assert profiles.delete_profile(p["id"], "someone-else") is False


def test_demo_profile_cannot_be_deleted():
    assert profiles.delete_profile(profiles.DEFAULT_PROFILE_ID, "anyone") is False


def test_list_profiles_scopes_to_owner():
    p1 = profiles.create_profile(owner_id="owner-3", name="Owner3 house", lat=1, lon=1, household_size=4, tier1_limit_gal=4000)
    visible_to_owner = [p["id"] for p in profiles.list_profiles("owner-3")]
    visible_to_stranger = [p["id"] for p in profiles.list_profiles("someone-else")]
    assert p1["id"] in visible_to_owner
    assert p1["id"] not in visible_to_stranger
    assert profiles.DEFAULT_PROFILE_ID in visible_to_owner
    assert profiles.DEFAULT_PROFILE_ID in visible_to_stranger
