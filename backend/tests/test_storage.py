from uuid import uuid4
from types import SimpleNamespace

from app.services.storage_service import PrivateStorage


def test_local_private_storage_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.storage_service.get_settings", lambda: SimpleNamespace(storage_bucket="test", storage_endpoint=None, storage_access_key=None, storage_secret_key=None, storage_local_root=str(tmp_path)))
    storage = PrivateStorage()
    key = storage.create_key(uuid4(), ".pdf")
    storage.put(key, b"resume")
    assert storage.get(key) == b"resume"
    storage.delete(key)
    assert not (tmp_path / key).exists()