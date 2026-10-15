"""
Sync Module - S3 Backup Sync

Merges the local cache with a copy held in an S3 bucket:
- Scans both sides and compares files by MD5
- Copies files that exist on only one side
- Reports files whose contents differ, and replaces them only when asked

S3 keys mirror the local cache under a season prefix:
    <season>/cache/gw<N>/<file>.json
"""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional

from . import storage

MODES = ("both", "save", "load")

_GAMEWEEK_DIR = re.compile(r"^gw\d+$")


@dataclass
class SyncPlan:
    """How each cache file compares between the local cache and S3."""
    local_only: List[str] = field(default_factory=list)
    remote_only: List[str] = field(default_factory=list)
    identical: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)


@dataclass
class Transfers:
    """The files a sync run copies in each direction."""
    uploads: List[str]
    downloads: List[str]
    # Conflicting files included in uploads or downloads
    overwritten: List[str]
    # Conflicting files left unchanged on both sides
    skipped_conflicts: List[str]


def current_season(today: Optional[date] = None) -> str:
    """
    Season label for a date, e.g. "2026-27".

    A season is taken to start in July, shortly before the FPL game opens.

    Args:
        today: Date to use (default: today)

    Returns:
        str: Season label
    """
    today = today or date.today()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def remote_prefix(season: str) -> str:
    """S3 key prefix that holds the cache for a season."""
    return f"{season}/cache/"


def is_cache_path(path: str) -> bool:
    """True for a path like "gw1/league_123.json", relative to the cache directory."""
    parts = path.split("/")
    return len(parts) == 2 and bool(_GAMEWEEK_DIR.match(parts[0])) and parts[1].endswith(".json")


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _local_path(path: str) -> str:
    return os.path.join(storage.get_data_dir(), "cache", *path.split("/"))


def scan_local_cache() -> Dict[str, str]:
    """
    Hash every cache file in the local cache.

    Only JSON files directly inside gw<N> directories are included.

    Returns:
        dict: Path relative to the cache directory (e.g. "gw1/bootstrap.json") to MD5 hex
    """
    cache_dir = os.path.join(storage.get_data_dir(), "cache")
    if not os.path.isdir(cache_dir):
        return {}

    files = {}
    for gw_dir in os.listdir(cache_dir):
        gw_path = os.path.join(cache_dir, gw_dir)
        if not (_GAMEWEEK_DIR.match(gw_dir) and os.path.isdir(gw_path)):
            continue
        for name in os.listdir(gw_path):
            file_path = os.path.join(gw_path, name)
            if name.endswith(".json") and os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    files[f"{gw_dir}/{name}"] = _md5(f.read())
    return files


def scan_remote(client, bucket: str, season: str) -> Dict[str, str]:
    """
    Hash every cache file stored in S3 for a season.

    Uses the object ETag, which is the MD5 of the contents for objects uploaded
    in a single part. Objects uploaded in multiple parts are downloaded and hashed.

    Args:
        client: boto3 S3 client
        bucket: Bucket name
        season: Season label

    Returns:
        dict: Path relative to the cache directory to MD5 hex
    """
    prefix = remote_prefix(season)
    files = {}
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            path = obj["Key"][len(prefix):]
            if not is_cache_path(path):
                continue
            etag = obj["ETag"].strip('"')
            if "-" in etag:
                body = client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
                etag = _md5(body)
            files[path] = etag
    return files


def plan_sync(local: Dict[str, str], remote: Dict[str, str]) -> SyncPlan:
    """
    Compare local and remote file hashes.

    Args:
        local: Output of scan_local_cache()
        remote: Output of scan_remote()

    Returns:
        SyncPlan: Each path placed in exactly one list, sorted
    """
    plan = SyncPlan()
    for path in sorted(set(local) | set(remote)):
        if path not in remote:
            plan.local_only.append(path)
        elif path not in local:
            plan.remote_only.append(path)
        elif local[path] == remote[path]:
            plan.identical.append(path)
        else:
            plan.conflicts.append(path)
    return plan


def select_transfers(plan: SyncPlan, mode: str, overwrite: bool = False) -> Transfers:
    """
    Choose which files to copy.

    "both" copies files that exist on only one side, in both directions.
    "save" only uploads and "load" only downloads. With overwrite, conflicting
    files are also copied in that direction, replacing the other side's copy.

    Args:
        plan: Output of plan_sync()
        mode: One of MODES
        overwrite: Replace conflicting files in the direction given by mode

    Returns:
        Transfers: Files to upload and download

    Raises:
        ValueError: If mode is unknown, or overwrite is used with "both"
    """
    if mode not in MODES:
        raise ValueError(f"Unknown sync mode: {mode}")
    if overwrite and mode == "both":
        raise ValueError("overwrite needs a direction ('save' or 'load')")

    uploads = list(plan.local_only) if mode in ("both", "save") else []
    downloads = list(plan.remote_only) if mode in ("both", "load") else []
    overwritten = list(plan.conflicts) if overwrite else []

    if mode == "save":
        uploads = sorted(uploads + overwritten)
    elif mode == "load":
        downloads = sorted(downloads + overwritten)

    return Transfers(
        uploads=uploads,
        downloads=downloads,
        overwritten=overwritten,
        skipped_conflicts=[] if overwrite else list(plan.conflicts),
    )


def upload_file(client, bucket: str, season: str, path: str) -> None:
    """Upload one cache file, given as a path relative to the cache directory."""
    with open(_local_path(path), "rb") as f:
        client.put_object(
            Bucket=bucket,
            Key=remote_prefix(season) + path,
            Body=f.read(),
            ContentType="application/json",
        )


def download_file(client, bucket: str, season: str, path: str) -> None:
    """Download one cache file, given as a path relative to the cache directory."""
    body = client.get_object(Bucket=bucket, Key=remote_prefix(season) + path)["Body"].read()
    dest = _local_path(path)
    dest_dir = os.path.dirname(dest)
    os.makedirs(dest_dir, exist_ok=True)

    # Write to a temporary file first so an interrupted download can't leave a partial JSON file
    fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, dest)
    except BaseException:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def execute_transfers(client, bucket: str, season: str, transfers: Transfers,
                      progress: Optional[Callable[[str], None]] = None) -> None:
    """
    Copy the selected files.

    Args:
        client: boto3 S3 client
        bucket: Bucket name
        season: Season label
        transfers: Output of select_transfers()
        progress: Called with each path after it is copied
    """
    for path in transfers.uploads:
        upload_file(client, bucket, season, path)
        if progress:
            progress(path)
    for path in transfers.downloads:
        download_file(client, bucket, season, path)
        if progress:
            progress(path)


def make_client(profile: str):
    """Create an S3 client using credentials from the named AWS CLI profile."""
    import boto3
    return boto3.Session(profile_name=profile).client("s3")
