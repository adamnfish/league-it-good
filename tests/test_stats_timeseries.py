"""
Tests for stats_timeseries.py

All functions are tested with synthetic data via monkeypatching of
load_gameweek_data — no real cache or FPL API needed.

Run with: python -m pytest src/tests/test_stats_timeseries.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from src import stats_timeseries as ts


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

def make_gw_data(gameweek: int, standings: list[dict]) -> dict:
    """Build a minimal load_gameweek_data return value."""
    return {
        "gameweek": gameweek,
        "league_data": {
            "standings": {
                "results": standings,
            }
        },
        "bootstrap_data": {},
    }


def make_manager(name: str, event_total: int, total: int) -> dict:
    """Build a minimal standings manager entry."""
    return {
        "player_name": name,
        "event_total": event_total,
        "total": total,
    }


# Reusable fixture: three managers over three gameweeks
MANAGERS_GW1 = [
    make_manager("Adam", 60, 60),
    make_manager("Beth", 50, 50),
    make_manager("Carl", 40, 40),
]
MANAGERS_GW2 = [
    make_manager("Adam", 45, 105),
    make_manager("Beth", 70, 120),
    make_manager("Carl", 55, 95),
]
MANAGERS_GW3 = [
    make_manager("Adam", 80, 185),
    make_manager("Beth", 40, 160),
    make_manager("Carl", 60, 155),
]

GW_DATA = {
    1: make_gw_data(1, MANAGERS_GW1),
    2: make_gw_data(2, MANAGERS_GW2),
    3: make_gw_data(3, MANAGERS_GW3),
}


def fake_load(league_id: int, gameweek: int):
    return GW_DATA.get(gameweek)


# ---------------------------------------------------------------------------
# calculate_weekly_scores
# ---------------------------------------------------------------------------

class TestCalculateWeeklyScores:
    def test_returns_all_managers(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_scores(12345, [1, 2, 3])
        assert set(result.keys()) == {"Adam", "Beth", "Carl"}

    def test_correct_scores_per_gameweek(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_scores(12345, [1, 2, 3])
        assert result["Adam"] == [(1, 60), (2, 45), (3, 80)]
        assert result["Beth"] == [(1, 50), (2, 70), (3, 40)]
        assert result["Carl"] == [(1, 40), (2, 55), (3, 60)]

    def test_results_are_sorted_chronologically(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_scores(12345, [3, 1, 2])  # unsorted input
        gws = [gw for gw, _ in result["Adam"]]
        assert gws == sorted(gws)

    def test_missing_gameweek_skipped(self):
        def sparse_load(league_id, gameweek):
            return GW_DATA.get(gameweek) if gameweek != 2 else None

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=sparse_load):
            result = ts.calculate_weekly_scores(12345, [1, 2, 3])
        # GW2 missing — Adam should only have GW1 and GW3
        assert len(result["Adam"]) == 2
        assert (2, 45) not in result["Adam"]

    def test_empty_gameweeks_returns_empty(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_scores(12345, [])
        assert result == {}

    def test_single_gameweek(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_scores(12345, [1])
        assert result["Adam"] == [(1, 60)]


# ---------------------------------------------------------------------------
# calculate_weekly_rankings
# ---------------------------------------------------------------------------

class TestCalculateWeeklyRankings:
    def test_returns_all_managers(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_rankings(12345, [1, 2, 3])
        assert set(result.keys()) == {"Adam", "Beth", "Carl"}

    def test_gw1_rankings(self):
        # Adam 60 total → 1st, Beth 50 → 2nd, Carl 40 → 3rd
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_rankings(12345, [1])
        assert result["Adam"] == [(1, 1)]
        assert result["Beth"] == [(1, 2)]
        assert result["Carl"] == [(1, 3)]

    def test_gw2_rankings(self):
        # Beth 120 → 1st, Adam 105 → 2nd, Carl 95 → 3rd
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_rankings(12345, [2])
        assert result["Beth"] == [(2, 1)]
        assert result["Adam"] == [(2, 2)]
        assert result["Carl"] == [(2, 3)]

    def test_tie_gives_same_rank(self):
        tied_data = {1: make_gw_data(1, [
            make_manager("Adam", 60, 60),
            make_manager("Beth", 60, 60),  # tied with Adam
            make_manager("Carl", 40, 40),
        ])}

        def tied_load(league_id, gameweek):
            return tied_data.get(gameweek)

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=tied_load):
            result = ts.calculate_weekly_rankings(12345, [1])
        assert result["Adam"][0][1] == 1
        assert result["Beth"][0][1] == 1
        # Carl should be 3rd (rank skips 2)
        assert result["Carl"][0][1] == 3

    def test_results_sorted_chronologically(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_rankings(12345, [3, 1, 2])
        gws = [gw for gw, _ in result["Adam"]]
        assert gws == sorted(gws)

    def test_missing_gameweek_skipped(self):
        def sparse_load(league_id, gameweek):
            return GW_DATA.get(gameweek) if gameweek != 2 else None

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=sparse_load):
            result = ts.calculate_weekly_rankings(12345, [1, 2, 3])
        assert len(result["Adam"]) == 2


# ---------------------------------------------------------------------------
# calculate_cumulative_points
# ---------------------------------------------------------------------------

class TestCalculateCumulativePoints:
    def test_running_totals_correct(self):
        weekly = {
            "Adam": [(1, 60), (2, 45), (3, 80)],
            "Beth": [(1, 50), (2, 70), (3, 40)],
        }
        result = ts.calculate_cumulative_points(weekly)
        # Series is prepended with a (0, 0) origin so all line charts
        # start from the same point.
        assert result["Adam"] == [(0, 0), (1, 60), (2, 105), (3, 185)]
        assert result["Beth"] == [(0, 0), (1, 50), (2, 120), (3, 160)]

    def test_single_gameweek(self):
        weekly = {"Adam": [(1, 60)]}
        result = ts.calculate_cumulative_points(weekly)
        assert result["Adam"] == [(0, 0), (1, 60)]

    def test_empty_input(self):
        result = ts.calculate_cumulative_points({})
        assert result == {}

    def test_out_of_order_input_sorted(self):
        # Input not sorted — cumulative should still work correctly
        weekly = {"Adam": [(3, 80), (1, 60), (2, 45)]}
        result = ts.calculate_cumulative_points(weekly)
        assert result["Adam"] == [(0, 0), (1, 60), (2, 105), (3, 185)]

    def test_does_not_mutate_input(self):
        weekly = {"Adam": [(1, 60), (2, 45)]}
        original = [t for t in weekly["Adam"]]
        ts.calculate_cumulative_points(weekly)
        assert weekly["Adam"] == original


# ---------------------------------------------------------------------------
# calculate_weekly_wins_losses
# ---------------------------------------------------------------------------

class TestCalculateWeeklyWinsLosses:
    def test_returns_all_managers(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        assert set(result.keys()) == {"Adam", "Beth", "Carl"}

    def test_each_result_has_correct_keys(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1])
        assert set(result["Adam"].keys()) == {"wins", "losses", "mid"}

    def test_win_counts(self):
        # GW1: Adam wins (60), Carl loses (40)
        # GW2: Beth wins (70), Carl loses (45 — wait, Adam has 45, Carl 55)
        # Actually: GW2 Beth=70 wins, Adam=45 loses
        # GW3: Adam wins (80), Beth loses (40)
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        assert result["Adam"]["wins"] == 2   # GW1, GW3
        assert result["Beth"]["wins"] == 1   # GW2
        assert result["Carl"]["wins"] == 0

    def test_loss_counts(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        assert result["Carl"]["losses"] == 1   # GW1 (40)
        assert result["Adam"]["losses"] == 1   # GW2 (45)
        assert result["Beth"]["losses"] == 1   # GW3 (40)

    def test_mid_counts(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        # GW1: Adam wins, Beth mid, Carl loses
        # GW2: Beth wins, Carl mid, Adam loses
        # GW3: Adam wins, Carl mid, Beth loses
        assert result["Adam"]["mid"] == 0   # won or lost every week
        assert result["Beth"]["mid"] == 1   # mid only in GW1
        assert result["Carl"]["mid"] == 2   # mid in GW2 and GW3

    def test_wins_losses_mid_sum_to_total_gameweeks(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        for manager, counts in result.items():
            assert counts["wins"] + counts["losses"] + counts["mid"] == 3

    def test_tied_win_both_get_win(self):
        tied_data = {1: make_gw_data(1, [
            make_manager("Adam", 60, 60),
            make_manager("Beth", 60, 60),
            make_manager("Carl", 40, 40),
        ])}

        def tied_load(league_id, gameweek):
            return tied_data.get(gameweek)

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=tied_load):
            result = ts.calculate_weekly_wins_losses(12345, [1])
        assert result["Adam"]["wins"] == 1
        assert result["Beth"]["wins"] == 1

    def test_two_managers_one_tied_as_loss(self):
        tied_loss_data = {1: make_gw_data(1, [
            make_manager("Adam", 60, 60),
            make_manager("Beth", 40, 40),
            make_manager("Carl", 40, 40),
        ])}

        def tied_load(league_id, gameweek):
            return tied_loss_data.get(gameweek)

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=tied_load):
            result = ts.calculate_weekly_wins_losses(12345, [1])
        assert result["Beth"]["losses"] == 1
        assert result["Carl"]["losses"] == 1

    def test_missing_gameweek_skipped(self):
        def sparse_load(league_id, gameweek):
            return GW_DATA.get(gameweek) if gameweek != 2 else None

        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=sparse_load):
            result = ts.calculate_weekly_wins_losses(12345, [1, 2, 3])
        for manager in result.values():
            assert manager["wins"] + manager["losses"] + manager["mid"] == 2


# ---------------------------------------------------------------------------
# calculate_score_consistency
# ---------------------------------------------------------------------------

class TestCalculateScoreConsistency:
    def test_returns_all_managers(self):
        weekly = {
            "Adam": [(1, 60), (2, 45), (3, 80)],
            "Beth": [(1, 50), (2, 70), (3, 40)],
        }
        result = ts.calculate_score_consistency(weekly)
        assert set(result.keys()) == {"Adam", "Beth"}

    def test_correct_keys(self):
        weekly = {"Adam": [(1, 60), (2, 40)]}
        result = ts.calculate_score_consistency(weekly)
        assert set(result["Adam"].keys()) == {"mean", "std", "high", "low", "range"}

    def test_mean_correct(self):
        weekly = {"Adam": [(1, 60), (2, 40), (3, 50)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["mean"] == pytest.approx(50.0)

    def test_high_and_low(self):
        weekly = {"Adam": [(1, 60), (2, 40), (3, 80)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["high"] == 80.0
        assert result["Adam"]["low"] == 40.0

    def test_range_is_high_minus_low(self):
        weekly = {"Adam": [(1, 60), (2, 40), (3, 80)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["range"] == pytest.approx(40.0)

    def test_std_zero_for_identical_scores(self):
        weekly = {"Adam": [(1, 50), (2, 50), (3, 50)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["std"] == pytest.approx(0.0)

    def test_std_positive_for_varied_scores(self):
        weekly = {"Adam": [(1, 60), (2, 40), (3, 80)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["std"] > 0

    def test_single_gameweek(self):
        weekly = {"Adam": [(1, 60)]}
        result = ts.calculate_score_consistency(weekly)
        assert result["Adam"]["mean"] == 60.0
        assert result["Adam"]["std"] == 0.0
        assert result["Adam"]["high"] == 60.0
        assert result["Adam"]["low"] == 60.0

    def test_empty_manager_skipped(self):
        weekly = {"Adam": [], "Beth": [(1, 50)]}
        result = ts.calculate_score_consistency(weekly)
        assert "Adam" not in result
        assert "Beth" in result

    def test_empty_input(self):
        result = ts.calculate_score_consistency({})
        assert result == {}


# ---------------------------------------------------------------------------
# calculate_all_timeseries (integration)
# ---------------------------------------------------------------------------

class TestCalculateAllTimeseries:
    def test_returns_all_keys(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_all_timeseries(12345, [1, 2, 3])
        assert set(result.keys()) == {
            "weekly_scores",
            "weekly_rankings",
            "cumulative_points",
            "wins_losses",
            "consistency",
        }

    def test_cumulative_derived_from_weekly_scores(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_all_timeseries(12345, [1, 2, 3])
        # Adam: 60 + 45 + 80 = 185 cumulative at GW3
        cumulative = result["cumulative_points"]
        assert cumulative["Adam"][-1] == (3, 185)

    def test_weekly_scores_and_cumulative_consistent(self):
        with patch("src.stats_timeseries.stats.load_gameweek_data", side_effect=fake_load):
            result = ts.calculate_all_timeseries(12345, [1, 2, 3])
        weekly = result["weekly_scores"]
        cumulative = result["cumulative_points"]
        for manager in weekly:
            total_from_weekly = sum(pts for _, pts in weekly[manager])
            final_cumulative = cumulative[manager][-1][1]
            assert total_from_weekly == final_cumulative
