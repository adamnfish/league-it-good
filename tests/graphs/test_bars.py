"""
Tests for graphs/charts/bars.py

Data reshaping and sorting logic is tested precisely.
Render functions are smoke-tested for PNG output and graceful edge cases.

Run with: python -m pytest tests/graphs/test_bars.py -v
"""

from __future__ import annotations

import pytest
import matplotlib
matplotlib.use("Agg")

from src.graphs.charts.bars import (
    render_ranked_bar,
    render_consistency_bar,
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


BENCH_DATA = [
    ("Adam", 88),
    ("Sarah", 71),
    ("Mike", 55),
    ("Dave", 32),
]

CONSISTENCY = {
    "Adam": {"mean": 65.2, "std": 8.1,  "high": 91.0, "low": 42.0, "range": 49.0},
    "Sarah": {"mean": 61.8, "std": 14.3, "high": 102.0, "low": 28.0, "range": 74.0},
    "Mike": {"mean": 58.4, "std": 11.2, "high": 88.0, "low": 30.0, "range": 58.0},
    "Dave": {"mean": 54.0, "std": 6.5,  "high": 72.0, "low": 38.0, "range": 34.0},
}


# ---------------------------------------------------------------------------
# render_ranked_bar
# ---------------------------------------------------------------------------

class TestRenderRankedBar:
    def test_produces_png(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "bench.png"
        render_ranked_bar("Bench Points", BENCH_DATA, config, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_empty_data_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "empty.png"
        render_ranked_bar("Empty", [], config, output)
        assert not output.exists()

    def test_single_manager(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "single.png"
        render_ranked_bar("Single", [("Adam", 88)], config, output)
        assert output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        config = make_config(["Adam"])  # Sarah not in config
        output = tmp_path / "fallback.png"
        render_ranked_bar("Bench Points", BENCH_DATA, config, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "bench.png"
        render_ranked_bar("Bench Points", BENCH_DATA, config, output)
        assert output.exists()

    def test_all_zeros_renders(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "zeros.png"
        data = [(name, 0) for name in ALL_MANAGERS]
        render_ranked_bar("Zero Points", data, config, output)
        assert output.exists()


# ---------------------------------------------------------------------------
# render_consistency_bar
# ---------------------------------------------------------------------------

class TestRenderConsistencyBar:
    def test_produces_png(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "consistency.png"
        render_consistency_bar(CONSISTENCY, config, output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_empty_data_does_not_crash(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "empty.png"
        render_consistency_bar({}, config, output)
        assert not output.exists()

    def test_single_manager(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "single.png"
        render_consistency_bar({"Adam": CONSISTENCY["Adam"]}, config, output)
        assert output.exists()

    def test_zero_std_renders(self, tmp_path):
        # All identical scores — std = 0, range line collapses to a point
        config = make_config(["Adam"])
        output = tmp_path / "zero_std.png"
        render_consistency_bar({
            "Adam": {"mean": 60.0, "std": 0.0,
                     "high": 60.0, "low": 60.0, "range": 0.0}
        }, config, output)
        assert output.exists()

    def test_sorted_by_std_ascending(self, tmp_path):
        """Most consistent manager (lowest std) appears first — smoke test."""
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "sorted.png"
        render_consistency_bar(CONSISTENCY, config, output)
        assert output.exists()

    def test_manager_not_in_config_uses_fallback(self, tmp_path):
        config = make_config(["Adam"])
        output = tmp_path / "fallback.png"
        render_consistency_bar(CONSISTENCY, config, output)
        assert output.exists()

    def test_creates_parent_dirs(self, tmp_path):
        config = make_config(ALL_MANAGERS)
        output = tmp_path / "nested" / "consistency.png"
        render_consistency_bar(CONSISTENCY, config, output)
        assert output.exists()
