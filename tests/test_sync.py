"""
Tests for sync.py

S3 is replaced by an in-memory fake client and the data directory by pytest's
tmp_path, so no AWS account or real cache is needed.

Run with: uv run pytest tests/test_sync.py -v
"""

from __future__ import annotations

import hashlib
import io
import json
from datetime import date

import pytest
from click.testing import CliRunner

from src import main, storage, sync

BUCKET = "test-bucket"
SEASON = "2026-27"


class FakeS3:
    """The parts of the boto3 S3 client that sync uses, backed by a dict of key to bytes."""

    def __init__(self, objects: dict | None = None, etags: dict | None = None):
        self.objects = dict(objects or {})
        self.etags = dict(etags or {})
        self.puts: list[str] = []

    def get_paginator(self, name: str):
        assert name == "list_objects_v2"
        return self

    def paginate(self, Bucket: str, Prefix: str):
        assert Bucket == BUCKET
        keys = sorted(k for k in self.objects if k.startswith(Prefix))
        # Split into two pages so the tests cover paging
        middle = len(keys) // 2
        for page_keys in (keys[:middle], keys[middle:]):
            if page_keys:
                yield {"Contents": [{"Key": k, "ETag": f'"{self._etag(k)}"'} for k in page_keys]}
            else:
                yield {}

    def _etag(self, key: str) -> str:
        return self.etags.get(key) or hashlib.md5(self.objects[key]).hexdigest()

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(self.objects[Key])}

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> None:
        self.objects[Key] = Body
        self.puts.append(Key)


def content(value) -> bytes:
    return json.dumps(value, indent=2).encode()


def remote_key(path: str) -> str:
    return f"{SEASON}/cache/{path}"


LOCAL_ONLY = "gw1/league_1.json"
REMOTE_ONLY = "gw2/league_1.json"
IDENTICAL = "gw1/bootstrap.json"
CONFLICT = "gw1/manager_1.json"

LOCAL_VERSION = content({"entry_history": {"points": 50}})
REMOTE_VERSION = content({"entry_history": {"points": 52}})


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "get_data_dir", lambda: str(tmp_path))
    return tmp_path


def write_local(data_dir, path: str, data: bytes) -> None:
    full_path = data_dir / "cache" / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(data)


def read_local(data_dir, path: str) -> bytes | None:
    full_path = data_dir / "cache" / path
    return full_path.read_bytes() if full_path.exists() else None


@pytest.fixture
def client(data_dir) -> FakeS3:
    """A local cache and bucket with one file in each state."""
    write_local(data_dir, LOCAL_ONLY, content({"league": {"name": "Local"}}))
    write_local(data_dir, IDENTICAL, content({"events": []}))
    write_local(data_dir, CONFLICT, LOCAL_VERSION)
    return FakeS3({
        remote_key(REMOTE_ONLY): content({"league": {"name": "Remote"}}),
        remote_key(IDENTICAL): content({"events": []}),
        remote_key(CONFLICT): REMOTE_VERSION,
    })


def run_sync(client: FakeS3, mode: str, overwrite: bool = False) -> sync.Transfers:
    plan = sync.plan_sync(sync.scan_local_cache(), sync.scan_remote(client, BUCKET, SEASON))
    transfers = sync.select_transfers(plan, mode, overwrite)
    sync.execute_transfers(client, BUCKET, SEASON, transfers)
    return transfers


def test_season_starts_in_july():
    assert sync.current_season(date(2026, 6, 30)) == "2025-26"
    assert sync.current_season(date(2026, 7, 1)) == "2026-27"
    assert sync.current_season(date(2099, 9, 1)) == "2099-00"


def test_plan_sync_classifies_each_file():
    local = {"gw1/a.json": "1", "gw1/same.json": "2", "gw1/diff.json": "3"}
    remote = {"gw2/b.json": "4", "gw1/same.json": "2", "gw1/diff.json": "5"}

    plan = sync.plan_sync(local, remote)

    assert plan == sync.SyncPlan(
        local_only=["gw1/a.json"],
        remote_only=["gw2/b.json"],
        identical=["gw1/same.json"],
        conflicts=["gw1/diff.json"],
    )


def test_scan_local_cache_only_reads_gameweek_json(data_dir):
    data = content({"league": {"name": "Test"}})
    write_local(data_dir, "gw1/league_1.json", data)
    write_local(data_dir, "gw1/notes.txt", b"notes")
    write_local(data_dir, "gw12/gw12.temp/league_1.json", data)
    write_local(data_dir, "gwx/league_1.json", data)
    write_local(data_dir, "other/league_1.json", data)

    assert sync.scan_local_cache() == {"gw1/league_1.json": hashlib.md5(data).hexdigest()}


def test_scan_local_cache_without_cache_dir(data_dir):
    assert sync.scan_local_cache() == {}


def test_scan_remote_only_reads_this_seasons_cache():
    data = content({"events": []})
    client = FakeS3({
        remote_key("gw1/bootstrap.json"): data,
        "2025-26/cache/gw1/bootstrap.json": data,
        f"{SEASON}/config/leagues/1.toml": b"[league]",
        remote_key("gw1/nested/bootstrap.json"): data,
    })

    assert sync.scan_remote(client, BUCKET, SEASON) == {"gw1/bootstrap.json": hashlib.md5(data).hexdigest()}


def test_scan_remote_hashes_multipart_objects():
    data = content({"events": []})
    client = FakeS3({remote_key("gw1/bootstrap.json"): data},
                    etags={remote_key("gw1/bootstrap.json"): "0123abcd-2"})

    assert sync.scan_remote(client, BUCKET, SEASON) == {"gw1/bootstrap.json": hashlib.md5(data).hexdigest()}


def test_both_copies_missing_files_and_leaves_conflicts(data_dir, client):
    transfers = run_sync(client, "both")

    assert remote_key(LOCAL_ONLY) in client.objects
    assert read_local(data_dir, REMOTE_ONLY) == client.objects[remote_key(REMOTE_ONLY)]
    assert read_local(data_dir, CONFLICT) == LOCAL_VERSION
    assert client.objects[remote_key(CONFLICT)] == REMOTE_VERSION
    assert transfers.skipped_conflicts == [CONFLICT]
    assert client.puts == [remote_key(LOCAL_ONLY)]


def test_save_only_uploads(data_dir, client):
    run_sync(client, "save")

    assert remote_key(LOCAL_ONLY) in client.objects
    assert read_local(data_dir, REMOTE_ONLY) is None
    assert client.objects[remote_key(CONFLICT)] == REMOTE_VERSION


def test_load_only_downloads(data_dir, client):
    run_sync(client, "load")

    assert remote_key(LOCAL_ONLY) not in client.objects
    assert read_local(data_dir, REMOTE_ONLY) is not None
    assert read_local(data_dir, CONFLICT) == LOCAL_VERSION


def test_save_overwrite_replaces_remote_conflicts(data_dir, client):
    transfers = run_sync(client, "save", overwrite=True)

    assert client.objects[remote_key(CONFLICT)] == LOCAL_VERSION
    assert read_local(data_dir, CONFLICT) == LOCAL_VERSION
    assert transfers.overwritten == [CONFLICT]
    assert transfers.skipped_conflicts == []


def test_load_overwrite_replaces_local_conflicts(data_dir, client):
    run_sync(client, "load", overwrite=True)

    assert read_local(data_dir, CONFLICT) == REMOTE_VERSION
    assert client.objects[remote_key(CONFLICT)] == REMOTE_VERSION
    assert client.puts == []


def test_overwrite_needs_a_direction():
    with pytest.raises(ValueError):
        sync.select_transfers(sync.SyncPlan(), "both", overwrite=True)


def test_download_leaves_no_temporary_files(data_dir, client):
    run_sync(client, "load", overwrite=True)

    assert sorted(p.name for p in (data_dir / "cache" / "gw1").iterdir()) == [
        "bootstrap.json", "league_1.json", "manager_1.json",
    ]


def invoke(*args: str):
    return CliRunner().invoke(main.cli, ["sync", *args, "--profile", "test", "--bucket", BUCKET, "--season", SEASON])


def test_cli_rejects_overwrite_without_mode():
    result = invoke("--overwrite")

    assert result.exit_code == 2
    assert "direction" in result.output


def test_cli_dry_run_changes_nothing(data_dir, client, monkeypatch):
    monkeypatch.setattr(sync, "make_client", lambda profile: client)

    result = invoke("--dry-run")

    assert result.exit_code == 0, result.output
    assert client.puts == []
    assert read_local(data_dir, REMOTE_ONLY) is None


def test_cli_load_overwrite_creates_safety_backup(data_dir, client, monkeypatch):
    monkeypatch.setattr(sync, "make_client", lambda profile: client)

    result = invoke("load", "--overwrite")

    assert result.exit_code == 0, result.output
    assert len(list((data_dir / "backups").glob("pre-sync-*.zip"))) == 1
    assert read_local(data_dir, CONFLICT) == REMOTE_VERSION
