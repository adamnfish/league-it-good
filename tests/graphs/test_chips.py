"""
Tests for graphs/charts/chips.py

reshape_chip_data is tested exhaustively as pure logic.
render_chip_chart is smoke-tested — we verify it produces a valid PNG
without asserting pixel values.

Run with: python -m pytest src/tests/graphs/test_chips.py -v
"""

from __future__ import annotations

import pytest
from pathlib import Path
import matplotlib
matplotlib.use("Agg")

from src.graphs.charts.chips import (
    reshape_chip_data,
    render_chip_chart,
    render_all_chip_charts,
    _format_segment_label,
)
from src.graphs.config import LeagueConfig, ManagerConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ALL_MANAGERS = ["Adam", "Sarah", "Mike", "Dave"]

# Normal chip usages: (manager_name, points, gameweek)
NORMAL_RAW = [
    ("Adam", 47, 8),
    ("Adam", 31, 22),   # Adam used it twice
    ("Sarah", 62, 14),   # Sarah used it once
    # Mike and Dave never used it
]

# TC usages: (manager_name, points, gameweek, player_name)
TC_RAW = [
    ("Adam", 18, 5, "Salah"),
    ("Sarah", 24, 12, "Haaland"),
    ("Sarah", 12, 30, "Palmer"),  # Sarah used TC twice
]


def make_config(names: list[str]) -> LeagueConfig:
    """Build a minimal LeagueConfig for the given manager names."""
    managers = [
        ManagerConfig(
            fpl_name=name,
            display_name=name,
            colour="#e63946",
        )
        for name in names
    ]
    return LeagueConfig(id=12345, managers=managers)


# ---------------------------------------------------------------------------
# _format_segment_label
# ---------------------------------------------------------------------------

class TestFormatSegmentLabel:
    def test_normal_chip_format(self):
        label = _format_segment_label(47, 8, None)
        assert label == "GW8 · 47pts"

    def test_triple_captain_format(self):
        label = _format_segment_label(18, 5, "Salah")
        assert label == "GW5 · Salah · 18pts"

    def test_large_gameweek_number(self):
        label = _format_segment_label(60, 38, None)
        assert "GW38" in label

    def test_zero_points(self):
        label = _format_segment_label(0, 1, None)
        assert "0pts" in label


# ---------------------------------------------------------------------------
# reshape_chip_data
# ---------------------------------------------------------------------------

class TestReshapeChipData:

    # --- Basic structure ---

    def test_returns_one_record_per_manager(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        assert len(result) == len(ALL_MANAGERS)

    def test_all_manager_names_present(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        names = {r["fpl_name"] for r in result}
        assert names == set(ALL_MANAGERS)

    def test_record_has_required_keys(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        for record in result:
            assert "fpl_name" in record
            assert "total" in record
            assert "usages" in record

    def test_usage_has_required_keys(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        adam = next(r for r in result if r["fpl_name"] == "Adam")
        for usage in adam["usages"]:
            assert "points" in usage
            assert "gameweek" in usage
            assert "player_name" in usage

    # --- Totals ---

    def test_total_is_sum_of_usage_points(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        adam = next(r for r in result if r["fpl_name"] == "Adam")
        assert adam["total"] == 47 + 31

    def test_unused_manager_has_zero_total(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        carl = next(r for r in result if r["fpl_name"] == "Mike")
        assert carl["total"] == 0

    def test_unused_manager_has_empty_usages(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        carl = next(r for r in result if r["fpl_name"] == "Mike")
        assert carl["usages"] == []

    # --- Sorting ---

    def test_sorted_by_total_descending(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        totals = [r["total"] for r in result]
        assert totals == sorted(totals, reverse=True)

    def test_zero_total_managers_at_bottom(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        # Mike and Dave have 0 — they should appear after Sarah (62) and Adam (78)
        zero_indices = [i for i, r in enumerate(result) if r["total"] == 0]
        nonzero_indices = [i for i, r in enumerate(result) if r["total"] > 0]
        assert all(zi > max(nonzero_indices) for zi in zero_indices)

    # --- Chronological ordering ---

    def test_usages_sorted_chronologically(self):
        # Adam used chip at GW22 then GW8 in the raw data — should come out GW8 first
        raw_reversed = [
            ("Adam", 31, 22),
            ("Adam", 47, 8),
        ]
        result = reshape_chip_data(raw_reversed, ["Adam"])
        adam = result[0]
        gameweeks = [u["gameweek"] for u in adam["usages"]]
        assert gameweeks == sorted(gameweeks)

    def test_earliest_usage_is_first(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        adam = next(r for r in result if r["fpl_name"] == "Adam")
        assert adam["usages"][0]["gameweek"] == 8
        assert adam["usages"][1]["gameweek"] == 22

    # --- Triple captain ---

    def test_tc_player_name_preserved(self):
        result = reshape_chip_data(TC_RAW, ALL_MANAGERS, is_triple_captain=True)
        adam = next(r for r in result if r["fpl_name"] == "Adam")
        assert adam["usages"][0]["player_name"] == "Salah"

    def test_normal_chip_player_name_is_none(self):
        result = reshape_chip_data(NORMAL_RAW, ALL_MANAGERS)
        adam = next(r for r in result if r["fpl_name"] == "Adam")
        for usage in adam["usages"]:
            assert usage["player_name"] is None

    def test_tc_two_usages_sorted_chronologically(self):
        result = reshape_chip_data(TC_RAW, ALL_MANAGERS, is_triple_captain=True)
        beth = next(r for r in result if r["fpl_name"] == "Sarah")
        assert len(beth["usages"]) == 2
        assert beth["usages"][0]["gameweek"] == 12
        assert beth["usages"][1]["gameweek"] == 30

    def test_tc_total_correct(self):
        result = reshape_chip_data(TC_RAW, ALL_MANAGERS, is_triple_captain=True)
        beth = next(r for r in result if r["fpl_name"] == "Sarah")
        assert beth["total"] == 24 + 12

    # --- Edge cases ---

    def test_empty_raw_all_managers_zero(self):
        result = reshape_chip_data([], ALL_MANAGERS)
        assert len(result) == len(ALL_MANAGERS)
        assert all(r["total"] == 0 for r in result)

    def test_empty_managers_list(self):
        result = reshape_chip_data(NORMAL_RAW, [])
        assert result == []

    def test_unknown_manager_in_raw_ignored(self):
        raw_with_unknown = NORMAL_RAW + [("Unknown Manager", 99, 1)]
        result = reshape_chip_data(raw_with_unknown, ALL_MANAGERS)
        names = {r["fpl_name"] for r in result}
        assert "Unknown Manager" not in names

    def test_single_manager_single_usage(self):
        result = reshape_chip_data([("Adam", 47, 8)], ["Adam"])
        assert len(result) == 1
        assert result[0]["total"] == 47
        assert len(result[0]["usages"]) == 1

    def test_all_managers_unused(self):
        result = reshape_chip_data([], ALL_MANAGERS)
        for record in result:
            assert record["total"] == 0
            assert record["usages"] == []


# ---------------------------------------------------------------------------
# render_chip_chart — smoke tests
# ---------------------------------------------------------------------------

class TestRenderChipChart:
    def test_produces_png_file(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "chip_test.png"
        render_chip_chart(
            chip_name="Bench Boost",
            raw_data=NORMAL_RAW,
            all_manager_names=ALL_MANAGERS,
            config=config,
            output_path=output,
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_produces_png_for_triple_captain(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "chip_tc.png"
        render_chip_chart(
            chip_name="Triple Captain",
            raw_data=TC_RAW,
            all_manager_names=ALL_MANAGERS,
            config=config,
            output_path=output,
            is_triple_captain=True,
        )
        assert output.exists()
        assert output.stat().st_size > 0

    def test_all_unused_still_renders(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "chip_unused.png"
        render_chip_chart(
            chip_name="Wildcard",
            raw_data=[],
            all_manager_names=ALL_MANAGERS,
            config=config,
            output_path=output,
        )
        assert output.exists()

    def test_single_manager_renders(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "chip_single.png"
        render_chip_chart(
            chip_name="Free Hit",
            raw_data=[("Adam", 55, 10)],
            all_manager_names=["Adam"],
            config=config,
            output_path=output,
        )
        assert output.exists()

    def test_empty_manager_list_does_not_crash(self, tmp_path):
        config = make_config([])
        output = tmp_path / "chip_empty.png"
        # Should return early without writing a file
        render_chip_chart(
            chip_name="Bench Boost",
            raw_data=[],
            all_manager_names=[],
            config=config,
            output_path=output,
        )
        # No file expected — early return
        assert not output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        # Config only has Adam — Sarah is unconfigured
        config = make_config(["Adam"])
        output = tmp_path / "chip_fallback.png"
        render_chip_chart(
            chip_name="Bench Boost",
            raw_data=NORMAL_RAW,
            all_manager_names=ALL_MANAGERS,
            config=config,
            output_path=output,
        )
        assert output.exists()

    def test_creates_parent_directories(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "dir" / "chip.png"
        render_chip_chart(
            chip_name="Bench Boost",
            raw_data=NORMAL_RAW,
            all_manager_names=ALL_MANAGERS,
            config=config,
            output_path=output,
        )
        assert output.exists()


# ---------------------------------------------------------------------------
# render_all_chip_charts — smoke test
# ---------------------------------------------------------------------------

class TestRenderAllChipCharts:
    def test_produces_four_files(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        chip_data = {
            "bench_boost": NORMAL_RAW,
            "triple_captain": TC_RAW,
            "free_hit": [("Adam", 88, 20)],
            "wildcard": [("Sarah", 55, 7), ("Mike", 40, 25)],
        }
        render_all_chip_charts(chip_data, ALL_MANAGERS, config, tmp_path)

        expected = [
            "chip_bench_boost.png",
            "chip_triple_captain.png",
            "chip_free_hit.png",
            "chip_wildcard.png",
        ]
        for filename in expected:
            assert (tmp_path / filename).exists(), f"Missing: {filename}"

    def test_missing_chip_key_uses_empty_list(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        # Partial chip_data — some keys missing
        chip_data = {
            "bench_boost": NORMAL_RAW,
            # triple_captain, free_hit, wildcard absent
        }
        # Should not raise
        render_all_chip_charts(chip_data, ALL_MANAGERS, config, tmp_path)
        assert (tmp_path / "chip_bench_boost.png").exists()
