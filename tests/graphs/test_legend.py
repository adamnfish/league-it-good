"""Tests for the legend (cover-sheet) chart."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from src.graphs.charts.legend import _derive_season, render_legend
from src.graphs.config import LeagueConfig, ManagerConfig


# ---------------------------------------------------------------------------
# _derive_season
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fake_now,expected",
    [
        # Pre-July dates belong to the previous season.
        (datetime(2026, 1, 15), "2025/26"),
        (datetime(2026, 5, 21), "2025/26"),
        (datetime(2026, 6, 30), "2025/26"),
        # July onwards starts the new season.
        (datetime(2026, 7, 1), "2026/27"),
        (datetime(2026, 8, 10), "2026/27"),
        (datetime(2026, 12, 31), "2026/27"),
        # Century boundary — two-digit suffix wraps correctly.
        (datetime(2099, 8, 1), "2099/00"),
    ],
)
def test_derive_season(fake_now, expected):
    assert _derive_season(fake_now) == expected


def test_derive_season_uses_now_by_default():
    # Smoke test: don't pin to a specific value, just check the format.
    result = _derive_season()
    assert len(result) == 7
    assert result[4] == "/"
    assert result[:4].isdigit()
    assert result[5:].isdigit()


# ---------------------------------------------------------------------------
# render_legend
# ---------------------------------------------------------------------------

def _make_config(names: list[str]) -> LeagueConfig:
    colours = ["#e63946", "#457b9d", "#2a9d8f", "#e9c46a"]
    return LeagueConfig(
        id=12345,
        name="Test League",
        managers=[
            ManagerConfig(
                fpl_name=n,
                display_name=n.split()[0],
                colour=colours[i % len(colours)],
            )
            for i, n in enumerate(names)
        ],
    )


def test_render_legend_produces_png(tmp_path):
    config = _make_config(["Adam Smith", "Dave Jones", "Sarah Mudlark", "Mike Brown"])
    output = tmp_path / "legend.png"

    render_legend(
        config=config,
        league_name="Test League",
        gameweek_range=(1, 27),
        season="2025/26",
        output_path=output,
    )

    assert output.exists()
    assert output.stat().st_size > 0


def test_render_legend_derives_season_when_none(tmp_path):
    config = _make_config(["Adam Smith"])
    output = tmp_path / "legend.png"

    render_legend(
        config=config,
        league_name="Test League",
        gameweek_range=(1, 5),
        season=None,
        output_path=output,
    )

    assert output.exists()


def test_render_legend_handles_empty_manager_list(tmp_path):
    config = LeagueConfig(id=12345, name="Empty", managers=[])
    output = tmp_path / "legend.png"

    render_legend(
        config=config,
        league_name="Empty League",
        gameweek_range=(1, 1),
        season="2025/26",
        output_path=output,
    )

    assert output.exists()


def test_render_legend_creates_parent_dirs(tmp_path):
    config = _make_config(["Adam Smith"])
    output = tmp_path / "nested" / "dir" / "legend.png"

    render_legend(
        config=config,
        league_name="Test",
        gameweek_range=(1, 1),
        season="2025/26",
        output_path=output,
    )

    assert output.exists()
