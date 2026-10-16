import pytest
import requests

import geocode


class FakeResponse:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


OPEN_METEO = {"results": [
    {"name": "Dixon", "admin1": "California", "latitude": 38.4455, "longitude": -121.8233},
    {"name": "Dixon", "admin1": "Illinois", "latitude": 41.8439, "longitude": -89.4793},
    {"name": "Dixon", "admin1": "California", "latitude": 38.4, "longitude": -121.8},
]}


@pytest.fixture(autouse=True)
def fresh_cache():
    geocode._search_cached.cache_clear()
    yield
    geocode._search_cached.cache_clear()


def fake_get(url, params=None, timeout=None):
    if "zippopotam" in url:
        if url.endswith("/00000"):
            return FakeResponse({}, 404)
        return FakeResponse({"places": [{"place name": "Dixon", "state": "California", "latitude": "38.44", "longitude": "-121.82"}]})
    return FakeResponse(OPEN_METEO)


@pytest.fixture
def mock_net(monkeypatch):
    monkeypatch.setattr(geocode.requests, "get", fake_get)


def test_city_search_returns_labels_and_coordinates_without_duplicates(mock_net):
    results = geocode.search("Dixon")
    assert [r["label"] for r in results] == ["Dixon, California", "Dixon, Illinois"]
    assert results[0]["lat"] == pytest.approx(38.4455)


def test_state_abbreviation_filters_results(mock_net):
    results = geocode.search("Dixon, CA")
    assert [r["label"] for r in results] == ["Dixon, California"]


def test_zip_code_lookup(mock_net):
    assert geocode.search("95620")[0]["label"] == "Dixon, California 95620"


def test_unknown_zip_and_short_queries_return_nothing(mock_net):
    assert geocode.search("00000") == []
    assert geocode.search("a") == []
    assert geocode.search("x" * 61) == []


def test_route_requires_sign_in(client):
    assert client.get("/api/geocode?q=Dixon").status_code == 401


def test_route_returns_results_for_signed_in_user(client, registered_user, mock_net):
    headers, _, _ = registered_user
    r = client.get("/api/geocode?q=Dixon", headers=headers)
    assert r.status_code == 200
    assert r.get_json()[0]["label"] == "Dixon, California"


def test_route_reports_unavailable_service(client, registered_user, monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(geocode.requests, "get", boom)
    headers, _, _ = registered_user
    r = client.get("/api/geocode?q=Dixon", headers=headers)
    assert r.status_code == 502
    assert "unavailable" in r.get_json()["error"]