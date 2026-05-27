"""
Tests for graphs/charts/lines.py

_ordinal_suffix is tested precisely as pure logic.
Render functions are smoke-tested — valid PNG produced, graceful edge cases.

Run with: python -m pytest src/tests/graphs/test_lines.py -v
"""

from __future__ import annotations

import pytest
import matplotlib
matplotlib.use("Agg")

from src.graphs.charts.lines import (
    render_weekly_scores,
    render_league_position,
    render_cumulative_points,
    render_all_line_charts,
    _ordinal_suffix,
)
from src.graphs.config import LeagueConfig, ManagerConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ALL_MANAGERS = ["Adam", "Sarah", "Mike", "Dave"]


def make_config(names: list[str]) -> LeagueConfig:
    managers = [
        ManagerConfig(fpl_name=n, display_name=n, colour="#e63946")
        for n in names
    ]
    return LeagueConfig(id=12345, managers=managers)


def make_config_multi_colour(names: list[str]) -> LeagueConfig:
    """Config with distinct colours per manager for visual test clarity."""
    colours = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a"]
    managers = [
        ManagerConfig(fpl_name=n, display_name=n, colour=colours[i % len(colours)])
        for i, n in enumerate(names)
    ]
    return LeagueConfig(id=12345, managers=managers)


# Realistic weekly scores: 4 managers, 10 gameweeks
WEEKLY_SCORES = {
    "Adam": [(1, 62), (2, 48), (3, 71), (4, 55), (5, 90),
             (6, 44), (7, 68), (8, 52), (9, 77), (10, 61)],
    "Sarah": [(1, 55), (2, 80), (3, 45), (4, 72), (5, 38),
             (6, 91), (7, 50), (8, 66), (9, 43), (10, 74)],
    "Mike": [(1, 48), (2, 55), (3, 60), (4, 48), (5, 75),
             (6, 52), (7, 82), (8, 40), (9, 58), (10, 55)],
    "Dave": [(1, 70), (2, 42), (3, 55), (4, 80), (5, 45),
             (6, 60), (7, 48), (8, 71), (9, 50), (10, 68)],
}

WEEKLY_RANKINGS = {
    "Adam": [(1, 2), (2, 3), (3, 2), (4, 3), (5, 1),
             (6, 3), (7, 2), (8, 3), (9, 1), (10, 2)],
    "Sarah": [(1, 3), (2, 1), (3, 4), (4, 2), (5, 4),
             (6, 1), (7, 3), (8, 2), (9, 4), (10, 1)],
    "Mike": [(1, 4), (2, 2), (3, 3), (4, 4), (5, 2),
             (6, 4), (7, 1), (8, 4), (9, 3), (10, 4)],
    "Dave": [(1, 1), (2, 4), (3, 1), (4, 1), (5, 3),
             (6, 2), (7, 4), (8, 1), (9, 2), (10, 3)],
}

CUMULATIVE = {
    "Adam": [(1, 62), (2, 110), (3, 181), (4, 236), (5, 326),
             (6, 370), (7, 438), (8, 490), (9, 567), (10, 628)],
    "Sarah": [(1, 55), (2, 135), (3, 180), (4, 252), (5, 290),
             (6, 381), (7, 431), (8, 497), (9, 540), (10, 614)],
    "Mike": [(1, 48), (2, 103), (3, 163), (4, 211), (5, 286),
             (6, 338), (7, 420), (8, 460), (9, 518), (10, 573)],
    "Dave": [(1, 70), (2, 112), (3, 167), (4, 247), (5, 292),
             (6, 352), (7, 400), (8, 471), (9, 521), (10, 589)],
}


# ---------------------------------------------------------------------------
# _ordinal_suffix
# ---------------------------------------------------------------------------

class TestOrdinalSuffix:
    def test_first(self):
        assert _ordinal_suffix(1) == "st"

    def test_second(self):
        assert _ordinal_suffix(2) == "nd"

    def test_third(self):
        assert _ordinal_suffix(3) == "rd"

    def test_fourth(self):
        assert _ordinal_suffix(4) == "th"

    def test_tenth(self):
        assert _ordinal_suffix(10) == "th"

    def test_eleventh_is_th(self):
        # 11th, 12th, 13th are exceptions — not 11st, 12nd, 13rd
        assert _ordinal_suffix(11) == "th"

    def test_twelfth_is_th(self):
        assert _ordinal_suffix(12) == "th"

    def test_thirteenth_is_th(self):
        assert _ordinal_suffix(13) == "th"

    def test_twenty_first_is_st(self):
        assert _ordinal_suffix(21) == "st"

    def test_twenty_second_is_nd(self):
        assert _ordinal_suffix(22) == "nd"

    def test_hundred_and_eleventh_is_th(self):
        assert _ordinal_suffix(111) == "th"

    def test_hundred_and_first_is_st(self):
        assert _ordinal_suffix(101) == "st"


# ---------------------------------------------------------------------------
# render_weekly_scores
# ---------------------------------------------------------------------------

class TestRenderWeeklyScores:
    def test_produces_png(self, tmp_path):
        config = make_config_multi_colour(ALL_MANAGERS)
        output = tmp_path / "weekly_scores.png"
        render_weekly_scores(WEEKLY_SCORES, config, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_empty_series_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "empty.png"
        render_weekly_scores({}, config, output)
        assert not output.exists()

    def test_single_manager(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "single.png"
        render_weekly_scores({"Adam": WEEKLY_SCORES["Adam"]}, config, output)
        assert output.exists()

    def test_single_gameweek(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "one_gw.png"
        render_weekly_scores({"Adam": [(1, 62)]}, config, output)
        assert output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        config = make_config(["Adam"])  # others not in config
        output = tmp_path / "fallback.png"
        render_weekly_scores(WEEKLY_SCORES, config, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "weekly.png"
        render_weekly_scores(WEEKLY_SCORES, config, output)
        assert output.exists()

    def test_manager_with_single_data_point(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "sparse.png"
        sparse = {
            "Adam": [(1, 62)],
            "Sarah": [(1, 55), (2, 80)],
        }
        render_weekly_scores(sparse, config, output)
        assert output.exists()


# ---------------------------------------------------------------------------
# render_league_position
# ---------------------------------------------------------------------------

class TestRenderLeaguePosition:
    def test_produces_png(self, tmp_path):
        config = make_config_multi_colour(ALL_MANAGERS)
        output = tmp_path / "league_position.png"
        render_league_position(WEEKLY_RANKINGS, config, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_empty_series_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "empty.png"
        render_league_position({}, config, output)
        assert not output.exists()

    def test_single_manager(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "single.png"
        render_league_position({"Adam": [(1, 1), (2, 1), (3, 1)]}, config, output)
        assert output.exists()

    def test_single_gameweek(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "one_gw.png"
        render_league_position(
            {"Adam": [(1, 1)], "Sarah": [(1, 2)], "Mike": [(1, 3)]},
            config, output,
        )
        assert output.exists()

    def test_all_tied_same_rank(self, tmp_path):
        config = make_config(["Adam", "Sarah"])
        output = tmp_path / "tied.png"
        render_league_position(
            {"Adam": [(1, 1), (2, 1)], "Sarah": [(1, 1), (2, 1)]},
            config, output,
        )
        assert output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "fallback.png"
        render_league_position(WEEKLY_RANKINGS, config, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "position.png"
        render_league_position(WEEKLY_RANKINGS, config, output)
        assert output.exists()

    def test_large_league(self, tmp_path):
        # 10 managers — checks y-axis scaling
        names = [f"Manager{i}" for i in range(1, 11)]
        config = make_config(names)
        output = tmp_path / "large_league.png"
        series = {name: [(gw, i + 1) for gw in range(1, 6)]
                  for i, name in enumerate(names)}
        render_league_position(series, config, output)
        assert output.exists()


# ---------------------------------------------------------------------------
# render_cumulative_points
# ---------------------------------------------------------------------------

class TestRenderCumulativePoints:
    def test_produces_png(self, tmp_path):
        config = make_config_multi_colour(ALL_MANAGERS)
        output = tmp_path / "cumulative.png"
        render_cumulative_points(CUMULATIVE, config, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_empty_series_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "empty.png"
        render_cumulative_points({}, config, output)
        assert not output.exists()

    def test_single_manager(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "single.png"
        render_cumulative_points({"Adam": CUMULATIVE["Adam"]}, config, output)
        assert output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "fallback.png"
        render_cumulative_points(CUMULATIVE, config, output)
        assert output.exists()

    def test_monotonically_increasing_data(self, tmp_path):
        # Cumulative should always go up — test with perfectly smooth data
        config = make_config(["Adam"])
        output = tmp_path / "mono.png"
        smooth = {"Adam": [(gw, gw * 60) for gw in range(1, 39)]}
        render_cumulative_points(smooth, config, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "cumulative.png"
        render_cumulative_points(CUMULATIVE, config, output)
        assert output.exists()


# ---------------------------------------------------------------------------
# render_all_line_charts
# ---------------------------------------------------------------------------

class TestRenderAllLineCharts:
    def test_produces_three_files(self, tmp_path):
        config = make_config_multi_colour(ALL_MANAGERS)
        timeseries = {
            "weekly_scores":    WEEKLY_SCORES,
            "weekly_rankings":  WEEKLY_RANKINGS,
            "cumulative_points": CUMULATIVE,
        }
        render_all_line_charts(timeseries, config, tmp_path)
        assert (tmp_path / "weekly_scores.png").exists()
        assert (tmp_path / "league_position.png").exists()
        assert (tmp_path / "cumulative_points.png").exists()

    def test_missing_key_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        render_all_line_charts({}, config, tmp_path)
        # No files expected — empty series returns early
        assert not (tmp_path / "weekly_scores.png").exists()

    def test_partial_timeseries(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        timeseries = {"weekly_scores": WEEKLY_SCORES}
        render_all_line_charts(timeseries, config, tmp_path)
        assert (tmp_path / "weekly_scores.png").exists()
