import pytest


@pytest.fixture(autouse=True)
def no_real_store(monkeypatch, tmp_path):
    """Nothing reads the learner's own store (data/panko.db) during tests: code that opens the default store on its
    own (your own pictures in a photo search) finds none."""
    import panko.store
    monkeypatch.setattr(panko.store, "DB_PATH", tmp_path / "no-store-in-tests.db")
