import pytest

import storage


class Snap:
    def __init__(self, data):
        self._d = data
        self.exists = data is not None

    def to_dict(self):
        return self._d


class Doc:
    def __init__(self, store, key):
        self.store, self.key = store, key

    def get(self):
        return Snap(self.store.get(self.key))

    def set(self, data):
        self.store[self.key] = dict(data)
        self.store["_writes"] = self.store.get("_writes", 0) + 1

    def delete(self):
        self.store.pop(self.key, None)


class Col:
    def __init__(self, store):
        self.store = store

    def document(self, key):
        return Doc(self.store, key)


class Client:
    def __init__(self):
        self.store = {}

    def collection(self, name):
        assert name == "usage_days"
        return Col(self.store)


@pytest.fixture
def fs(monkeypatch):
    client = Client()
    monkeypatch.setattr(storage, "_backend", "firestore")
    monkeypatch.setattr(storage, "_firestore_client", client)
    return client


def test_big_upload_is_one_write(fs):
    entries = {f"2020-{m:02d}-{d:02d}": float(m * d) for m in range(1, 13) for d in range(1, 29)}
    storage.save_usage("p1", entries)
    assert fs.store["_writes"] == 1
    assert storage.list_usage("p1") == entries


def test_replace_and_merge(fs):
    storage.save_usage("p1", {"2026-10-01": 100.0, "2026-10-02": 110.0})
    storage.save_usage("p1", {"2026-10-02": 120.0, "2026-10-03": 130.0})
    assert storage.list_usage("p1") == {"2026-10-01": 100.0, "2026-10-02": 120.0, "2026-10-03": 130.0}


def test_delete_days_and_all(fs):
    storage.save_usage("p1", {"2026-10-01": 1.0, "2026-10-02": 2.0})
    storage.delete_usage("p1", ["2026-10-01"])
    assert storage.list_usage("p1") == {"2026-10-02": 2.0}
    storage.delete_usage("p1", ["2026-10-02"])
    assert storage.list_usage("p1") == {}
    storage.save_usage("p1", {"2026-10-05": 5.0})
    storage.delete_usage("p1")
    assert storage.list_usage("p1") == {}


def test_households_are_separate(fs):
    storage.save_usage("a", {"2026-10-01": 1.0})
    storage.save_usage("b", {"2026-10-01": 9.0})
    assert storage.list_usage("a") == {"2026-10-01": 1.0}
