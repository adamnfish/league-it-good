"""
Tests for season.py, and the season checks in fpl.py and the CLI

The data directory is replaced by pytest's tmp_path and the FPL API by a fake
requests.get, so no real cache or network access is needed.

Run with: uv run pytest tests/test_season.py -v
"""

from __future__ import annotations

import json
import zipfile

import pytest
from click.testing import CliRunner

from src import fpl, main, season, storage


def bootstrap(start_year: int) -> dict:
    """Bootstrap data for the season starting in start_year, with its events out of order."""
    return {
        "events": [
            {"id": 38, "deadline_time": f"{start_year + 1}-05-24T13:30:00Z", "deadline_time_epoch": 1779629400},
            {"id": 1, "deadline_time": f"{start_year}-08-15T17:30:00Z", "deadline_time_epoch": 1755279000},
        ],
        "game_config": {"settings": {"price_change_deadlines": [f"{start_year - 1}-07-01T23:00:00Z"]}},
    }


LEAGUE = {
    "league": {"name": "Test League"},
    "standings": {"results": [{"entry": 1, "player_name": "Adam Smith"}]},
}


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "get_data_dir", lambda: str(tmp_path))
    monkeypatch.setattr(fpl, "_live_bootstrap", None)
    monkeypatch.setattr(fpl, "_live_season_checked", False)
    return tmp_path


def write_cache(data_dir, path: str, data: dict) -> None:
    full_path = data_dir / "cache" / path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(json.dumps(data, indent=2))


def write_backup(path, files: dict) -> None:
    with zipfile.ZipFile(path, "w") as zipf:
        for name, data in files.items():
            zipf.writestr(name, json.dumps(data, indent=2))


class FakeResponse:
    def __init__(self, data: dict):
        self.data = data

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self.data


class FakeApi:
    """Stands in for requests.get, serving bootstrap data for one season."""

    def __init__(self, start_year: int):
        self.start_year = start_year
        self.urls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        self.urls.append(url)
        if "bootstrap-static" in url:
            return FakeResponse(bootstrap(self.start_year))
        return FakeResponse({"entry_history": {"points": 50}})

    def bootstrap_requests(self) -> int:
        return sum("bootstrap-static" in url for url in self.urls)


@pytest.fixture
def api_2026(monkeypatch) -> FakeApi:
    api = FakeApi(2026)
    monkeypatch.setattr(fpl.requests, "get", api.get)
    return api


def invoke(*args: str):
    return CliRunner().invoke(main.cli, list(args))


def test_season_from_bootstrap_uses_first_deadline():
    assert season.season_from_bootstrap(bootstrap(2026)) == "2026-27"
    assert season.season_from_bootstrap(bootstrap(2099)) == "2099-00"


def test_season_from_bootstrap_without_events():
    assert season.season_from_bootstrap({"events": []}) is None


def test_is_season_label():
    assert season.is_season_label("2026-27")
    assert not season.is_season_label("2026-28")
    assert not season.is_season_label("2026")


def test_empty_cache_has_no_season(data_dir):
    assert season.get_cache_season() is None


def test_cache_season(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    write_cache(data_dir, "gw2/bootstrap.json", bootstrap(2026))
    write_cache(data_dir, "gw3/league_1.json", LEAGUE)

    assert season.cache_seasons() == {"2026-27": [1, 2]}
    assert season.get_cache_season() == "2026-27"


def test_mixed_cache_is_an_error(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    write_cache(data_dir, "gw12/bootstrap.json", bootstrap(2025))

    with pytest.raises(season.SeasonError, match="2025-26 in GW12; 2026-27 in GW1"):
        season.get_cache_season()


def test_backup_seasons(tmp_path):
    archive = tmp_path / "backup.zip"
    write_backup(archive, {"gw1/bootstrap.json": bootstrap(2025), "gw1/league_1.json": LEAGUE, "metadata.json": {}})

    assert season.backup_seasons(str(archive)) == {"2025-26": [1]}


def test_check_incoming(data_dir):
    # An empty cache accepts any season
    season.check_incoming("2025-26", "Test data")

    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    season.check_incoming("2026-27", "Test data")
    season.check_incoming(None, "Test data")

    with pytest.raises(season.SeasonError, match="start-new-season"):
        season.check_incoming("2025-26", "Test data")


def test_api_data_from_another_season_is_not_saved(data_dir, api_2026):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2025))

    with pytest.raises(season.SeasonError):
        fpl.fetch_manager_gameweek(1, 2)
    with pytest.raises(season.SeasonError):
        fpl.fetch_bootstrap_data(2)

    assert list((data_dir / "cache" / "gw2").iterdir()) == []


def test_api_data_from_the_cached_season_is_saved(data_dir, api_2026):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))

    fpl.fetch_manager_gameweek(1, 2)
    fpl.fetch_bootstrap_data(2)

    assert (data_dir / "cache" / "gw2" / "manager_1.json").exists()
    assert (data_dir / "cache" / "gw2" / "bootstrap.json").exists()
    assert api_2026.bootstrap_requests() == 1


def test_empty_cache_accepts_api_data_without_a_season_check(data_dir, api_2026):
    fpl.fetch_manager_gameweek(1, 1)

    assert (data_dir / "cache" / "gw1" / "manager_1.json").exists()
    assert api_2026.bootstrap_requests() == 0


def test_start_new_season_needs_a_season(data_dir):
    write_cache(data_dir, "gw1/league_1.json", LEAGUE)

    with pytest.raises(season.SeasonError):
        season.plan_new_season()


def test_start_new_season_moves_season_dirs(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    (data_dir / "summaries").mkdir()
    (data_dir / "summaries" / "league_1_gw1_summary.txt").write_text("summary")
    (data_dir / "config" / "leagues").mkdir(parents=True)
    (data_dir / "2025-26" / "cache").mkdir(parents=True)

    label, moves = season.plan_new_season()
    season.start_new_season(moves)

    assert label == "2026-27"
    assert sorted(p.name for p in data_dir.iterdir()) == ["2025-26", "2026-27"]
    assert sorted(p.name for p in (data_dir / "2026-27").iterdir()) == ["cache", "config", "summaries"]
    assert (data_dir / "2026-27" / "cache" / "gw1" / "bootstrap.json").exists()


def test_start_new_season_refuses_existing_destination(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    (data_dir / "summaries").mkdir()
    (data_dir / "2026-27" / "summaries").mkdir(parents=True)

    with pytest.raises(season.SeasonError, match="already exists"):
        season.plan_new_season()

    assert (data_dir / "cache").exists()
    assert (data_dir / "summaries").exists()


def test_cli_season_shows_cached_season(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))

    result = invoke("season")

    assert result.exit_code == 0, result.output
    assert "2026-27" in result.output


def test_cli_mixed_cache_is_reported_as_an_error(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    write_cache(data_dir, "gw12/bootstrap.json", bootstrap(2025))

    result = invoke("season")

    assert result.exit_code == 1
    assert "more than one season" in result.output


def test_cli_start_new_season_dry_run_moves_nothing(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))

    result = invoke("season", "start-new-season", "--dry-run")

    assert result.exit_code == 0, result.output
    assert (data_dir / "cache").exists()
    assert not (data_dir / "2026-27").exists()


def test_cli_start_new_season(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))

    result = invoke("season", "start-new-season")

    assert result.exit_code == 0, result.output
    assert not (data_dir / "cache").exists()
    assert (data_dir / "2026-27" / "cache" / "gw1" / "bootstrap.json").exists()


def test_cli_import_refuses_backup_from_another_season(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    archive = data_dir / "old.zip"
    write_backup(archive, {"gw2/bootstrap.json": bootstrap(2025), "gw2/league_1.json": LEAGUE})

    result = invoke("import", str(archive), "--file")

    assert result.exit_code == 1
    assert "2025-26" in result.output
    assert not (data_dir / "cache" / "gw2").exists()


def test_cli_leagues_shows_season(data_dir):
    write_cache(data_dir, "gw1/bootstrap.json", bootstrap(2026))
    write_cache(data_dir, "gw1/league_1.json", LEAGUE)

    result = invoke("leagues")

    assert result.exit_code == 0, result.output
    assert "Season 2026-27" in result.output
