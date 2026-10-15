"""
Season Module - Season Detection and Rollover

Works out which FPL season cached data belongs to, and keeps data from
different seasons apart:
- Reads the season from bootstrap data (the year of the first gameweek deadline)
- Finds the season held in the local cache and in backup archives
- Checks incoming data against the cache's season
- Moves a season's data aside, ready for the next season
"""

import os
import re
import shutil
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from . import storage

# Directories in the data directory that belong to a season
SEASON_DIRS = ("cache", "summaries", "graphs", "backups", "exports", "config")

_SEASON_LABEL = re.compile(r"^\d{4}-\d{2}$")
_GAMEWEEK_DIR = re.compile(r"^gw(\d+)$")
_DEADLINE_YEAR = re.compile(rb'"deadline_time"\s*:\s*"(\d{4})-')


class SeasonError(Exception):
    """Data from different seasons would be mixed, or the season can't be worked out."""


def season_label(start_year: int) -> str:
    """Label for the season starting in start_year, e.g. 2026 -> "2026-27"."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def is_season_label(value: str) -> bool:
    """True for a valid season label such as "2026-27"."""
    return bool(_SEASON_LABEL.match(value)) and season_label(int(value[:4])) == value


def season_from_bootstrap(data: Dict[str, Any]) -> Optional[str]:
    """
    Season of parsed bootstrap data.

    Args:
        data: Bootstrap data from the FPL API

    Returns:
        str: Season label from the year of the earliest gameweek deadline, or None if there are no events
    """
    deadlines = [event["deadline_time"] for event in data.get("events", []) if event.get("deadline_time")]
    if not deadlines:
        return None
    return season_label(int(min(deadlines)[:4]))


def _season_from_bootstrap_bytes(raw: bytes) -> Optional[str]:
    # Matching the deadlines directly is several times faster than parsing a 2MB bootstrap file
    years = _DEADLINE_YEAR.findall(raw)
    if not years:
        return None
    return season_label(int(min(years)))


def _add_season(seasons: Dict[str, List[int]], raw: bytes, gameweek: int) -> None:
    label = _season_from_bootstrap_bytes(raw)
    if label:
        seasons.setdefault(label, []).append(gameweek)


def cache_seasons() -> Dict[str, List[int]]:
    """
    Seasons of the bootstrap files in the local cache.

    Returns:
        dict: Season label to sorted list of gameweeks with bootstrap data from that season
    """
    cache_dir = os.path.join(storage.get_data_dir(), "cache")
    if not os.path.isdir(cache_dir):
        return {}

    seasons: Dict[str, List[int]] = {}
    for item in os.listdir(cache_dir):
        match = _GAMEWEEK_DIR.match(item)
        path = os.path.join(cache_dir, item, "bootstrap.json")
        if match and os.path.isfile(path):
            with open(path, "rb") as f:
                _add_season(seasons, f.read(), int(match.group(1)))
    return {label: sorted(gameweeks) for label, gameweeks in seasons.items()}


def backup_seasons(archive_path: str) -> Dict[str, List[int]]:
    """
    Seasons of the bootstrap files in a backup archive.

    Args:
        archive_path: Path to backup zip file

    Returns:
        dict: Season label to sorted list of gameweeks with bootstrap data from that season
    """
    seasons: Dict[str, List[int]] = {}
    with zipfile.ZipFile(archive_path, "r") as zipf:
        for name in zipf.namelist():
            parts = name.split("/")
            match = _GAMEWEEK_DIR.match(parts[0])
            if len(parts) == 2 and parts[1] == "bootstrap.json" and match:
                _add_season(seasons, zipf.read(name), int(match.group(1)))
    return {label: sorted(gameweeks) for label, gameweeks in seasons.items()}


def _single_season(seasons: Dict[str, List[int]], where: str) -> Optional[str]:
    if not seasons:
        return None
    if len(seasons) > 1:
        details = "; ".join(
            f"{label} in GW{', GW'.join(str(gw) for gw in gameweeks)}"
            for label, gameweeks in sorted(seasons.items())
        )
        raise SeasonError(f"{where} holds data from more than one season: {details}")
    return next(iter(seasons))


def get_cache_season() -> Optional[str]:
    """
    Season held in the local cache.

    Returns:
        str: Season label, or None if the cache has no bootstrap data

    Raises:
        SeasonError: If the cache holds bootstrap data from more than one season
    """
    return _single_season(cache_seasons(), "The cache")


def check_incoming(incoming: Optional[str], source: str) -> None:
    """
    Check that data about to be written to the cache is from the cache's season.

    Args:
        incoming: Season of the new data, or None if it isn't known
        source: Where the data comes from, for the error message (e.g. "The FPL API")

    Raises:
        SeasonError: If the cache holds data from a different season
    """
    if incoming is None:
        return
    cached = get_cache_season()
    if cached is not None and incoming != cached:
        raise SeasonError(
            f"{source} has {incoming} data, but the cache holds {cached} data. "
            f"Run 'lig season start-new-season' to move the {cached} data aside first."
        )


def check_backup(archive_path: str) -> Optional[str]:
    """
    Check that a backup archive is from the cache's season.

    Args:
        archive_path: Path to backup zip file

    Returns:
        str: The backup's season, or None if it has no bootstrap data

    Raises:
        SeasonError: If the backup mixes seasons, or is from a different season to the cache
    """
    label = _single_season(backup_seasons(archive_path), "This backup")
    check_incoming(label, "This backup")
    return label


def plan_new_season() -> Tuple[str, List[Tuple[str, str]]]:
    """
    Work out where each season directory moves to when starting a new season.

    Returns:
        tuple: (season label, list of (source, destination) paths)

    Raises:
        SeasonError: If the cache has no season, or a destination already exists
    """
    label = get_cache_season()
    if label is None:
        raise SeasonError("The cache has no bootstrap data, so there is no season to move aside.")

    data_dir = storage.get_data_dir()
    moves = []
    for name in SEASON_DIRS:
        source = os.path.join(data_dir, name)
        if not os.path.exists(source):
            continue
        destination = os.path.join(data_dir, label, name)
        if os.path.exists(destination):
            raise SeasonError(f"{destination} already exists. Move or merge it by hand, then run this again.")
        moves.append((source, destination))
    return label, moves


def start_new_season(moves: List[Tuple[str, str]]) -> None:
    """
    Move season directories aside.

    Args:
        moves: Output of plan_new_season()
    """
    for source, destination in moves:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(source, destination)
