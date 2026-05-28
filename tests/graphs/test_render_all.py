"""
Tests for graphs/__init__.py

render_all is integration-tested by patching the stats dependencies
directly on the src package so the lazy imports inside
render_all see mocks regardless of import order.

_get_all_manager_names is tested as pure logic.

Run with: python -m pytest src/tests/graphs/test_render_all.py -v
"""

from __future__ import annotations

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import matplotlib
matplotlib.use("Agg")

import src                    # ensure the package is imported
import src.stats              # ensure attribute exists for patching
import src.stats_timeseries   # ensure attribute exists for patching
from src.graphs import _get_all_manager_names, render_all
from src.graphs.config import LeagueConfig, ManagerConfig


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

MANAGERS = ["Adam", "Sarah", "Mike", "Dave"]


def make_config(names: list[str]) -> LeagueConfig:
    managers = [
        ManagerConfig(fpl_name=n, display_name=n, colour="#e63946")
        for n in names
    ]
    return LeagueConfig(id=12345, managers=managers, name="Test League")


def make_standings(names: list[str]) -> list[dict]:
    return [
        {"player_name": n, "event_total": 60, "total": (i + 1) * 60, "entry": 1000 + i}
        for i, n in enumerate(names)
    ]


def make_gw_data(names: list[str]) -> dict:
    return {
        "gameweek": 1,
        "league_data": {
            "league": {"name": "Test League"},
            "standings": {"results": make_standings(names)},
        },
        "bootstrap_data": {"elements": []},
    }


def make_season_stats(names: list[str]) -> dict:
    pairs = [(n, 10) for n in names]
    return {
        "league_name": "Test League",
        "gameweeks_analyzed": [1, 2, 3],
        "gameweeks_skipped": [],
        "stats": {
            "most_wins":             {"winners": pairs, "gameweeks_processed": 3},
            "highest_bench_points":  {"totals": pairs, "gameweeks_processed": 3},
            "most_transfer_cost":    {"totals": pairs, "gameweeks_processed": 3},
            "best_position_scores":  {
                "defence": pairs, "midfield": pairs, "attack": pairs,
                "gameweeks_processed": 3,
            },
            "best_chip_returns": {
                "bench_boost": [], "triple_captain": [],
                "free_hit": [], "wildcard": [],
                "gameweeks_processed": 3,
            },
        },
    }


def make_timeseries(names: list[str]) -> dict:
    gws = [1, 2, 3]
    return {
        "weekly_scores":     {n: [(gw, 60) for gw in gws] for n in names},
        "weekly_rankings":   {n: [(gw, i + 1) for gw in gws] for i, n in enumerate(names)},
        "cumulative_points": {n: [(gw, gw * 60) for gw in gws] for n in names},
        "wins_losses":       {n: {"wins": 1, "losses": 1, "mid": 1} for n in names},
        "consistency":       {n: {"mean": 60.0, "std": 5.0, "high": 70.0,
                                  "low": 50.0, "range": 20.0} for n in names},
    }


def make_global_standing(names: list[str]) -> tuple[dict, int]:
    """Mirror calculate_global_standing: (standing, total_players)."""
    spread = 90.0 / max(len(names), 1)
    standing = {
        n: {
            "overall_rank": (i + 1) * 1000,
            "total_points": (len(names) - i) * 100,
            "percentile": 100.0 - i * spread,
        }
        for i, n in enumerate(names)
    }
    return standing, 11_000_000


def run_render_all(tmp_path: Path, names: list[str] = None) -> None:
    """
    Call render_all with mocked stats dependencies.

    Patches src.stats and src.stats_timeseries at the
    module attribute level — this is what the `from .. import stats`
    inside render_all will see regardless of sys.modules import order.
    """
    if names is None:
        names = MANAGERS

    mock_stats = MagicMock()
    mock_stats.load_gameweek_data.return_value = make_gw_data(names)
    mock_stats.calculate_season_statistics.return_value = make_season_stats(names)

    mock_ts = MagicMock()
    mock_ts.calculate_all_timeseries.return_value = make_timeseries(names)
    mock_ts.calculate_global_standing.return_value = make_global_standing(names)

    with (
        patch("src.stats", mock_stats),
        patch("src.stats_timeseries", mock_ts),
    ):
        render_all(
            league_id=12345,
            gameweeks=[1, 2, 3],
            config=make_config(names),
            output_dir=tmp_path,
            league_name="Test League",
            season="2025/26",
        )


# ---------------------------------------------------------------------------
# _get_all_manager_names
# ---------------------------------------------------------------------------

class TestGetAllManagerNames:
    def test_returns_names_from_first_valid_gameweek(self):
        mock = MagicMock()
        mock.load_gameweek_data.return_value = make_gw_data(MANAGERS)
        assert _get_all_manager_names(12345, [1, 2, 3], mock) == MANAGERS

    def test_skips_missing_gameweeks(self):
        mock = MagicMock()
        mock.load_gameweek_data.side_effect = [None, make_gw_data(MANAGERS)]
        assert _get_all_manager_names(12345, [1, 2], mock) == MANAGERS

    def test_returns_empty_when_no_data(self):
        mock = MagicMock()
        mock.load_gameweek_data.return_value = None
        assert _get_all_manager_names(12345, [1, 2, 3], mock) == []

    def test_returns_empty_for_empty_gameweeks(self):
        mock = MagicMock()
        assert _get_all_manager_names(12345, [], mock) == []
        mock.load_gameweek_data.assert_not_called()

    def test_preserves_standings_order(self):
        ordered = ["Dave", "Mike", "Sarah", "Adam"]
        mock = MagicMock()
        mock.load_gameweek_data.return_value = make_gw_data(ordered)
        assert _get_all_manager_names(12345, [1], mock) == ordered


# ---------------------------------------------------------------------------
# render_all — integration smoke tests
# ---------------------------------------------------------------------------

class TestRenderAll:

    def test_creates_output_directory(self, tmp_path):
        output = tmp_path / "graphs" / "12345"
        run_render_all(output)
        assert output.exists()

    def test_wins_and_losses_pngs_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "wins.png").exists()
        assert (tmp_path / "losses.png").exists()

    def test_bench_points_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "bench_points.png").exists()

    def test_transfer_costs_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "transfer_costs.png").exists()

    def test_position_breakdown_pngs_produced(self, tmp_path):
        run_render_all(tmp_path)
        for zone in ("defence", "midfield", "attack"):
            assert (tmp_path / f"position_{zone}.png").exists()

    def test_consistency_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "consistency.png").exists()

    def test_all_chip_pngs_produced(self, tmp_path):
        run_render_all(tmp_path)
        for chip in ("bench_boost", "triple_captain", "free_hit", "wildcard"):
            assert (tmp_path / f"chip_{chip}.png").exists()

    def test_weekly_scores_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "weekly_scores.png").exists()

    def test_league_position_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "league_position.png").exists()

    def test_cumulative_points_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "cumulative_points.png").exists()

    def test_all_pngs_produced(self, tmp_path):
        run_render_all(tmp_path)
        expected = {
            "legend.png",
            "wins.png", "losses.png",
            "bench_points.png", "transfer_costs.png",
            "position_defence.png", "position_midfield.png", "position_attack.png",
            "consistency.png",
            "chip_bench_boost.png", "chip_triple_captain.png",
            "chip_free_hit.png", "chip_wildcard.png",
            "weekly_scores.png", "league_position.png", "cumulative_points.png",
            "global_rank.png",
        }
        produced = {f.name for f in tmp_path.glob("*.png")}
        assert expected == produced

    def test_legend_png_produced(self, tmp_path):
        run_render_all(tmp_path)
        assert (tmp_path / "legend.png").exists()

    def test_single_manager_league(self, tmp_path):
        run_render_all(tmp_path, names=["Adam"])
        assert (tmp_path / "wins.png").exists()

    def test_large_league(self, tmp_path):
        names = [f"Manager{i}" for i in range(1, 13)]
        run_render_all(tmp_path, names=names)
        assert (tmp_path / "cumulative_points.png").exists()
