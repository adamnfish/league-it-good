"""
Graphs Package — render orchestrator

Ties together all chart modules into a dispatch dict keyed by chart name
(also the PNG basename). `render_all` iterates the dict; CLI callers can
filter to a single entry when rendering one chart.

Typical usage (from the CLI):
    from src.graphs import render_all
    render_all(league_id, gameweeks, league_config, output_dir)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import click

from .config import LeagueConfig
from .charts.bars import (
    render_ranked_bar,
    render_wins_losses_bar,
    render_position_breakdown,
    render_consistency_bar,
)
from .charts.chips import render_chip_chart
from .charts.legend import render_legend
from .charts.lines import (
    render_weekly_scores,
    render_league_position,
    render_cumulative_points,
)


# One-line summary per chart for CLI --list output and help text.
CHART_DESCRIPTIONS: Dict[str, str] = {
    "legend":            "Cover sheet: league name, season, manager list with colours",
    "wins_losses":       "Stacked bar of weekly wins / losses / mid-table per manager",
    "bench_points":      "Bench points left unused, ranked highest to lowest",
    "transfer_costs":    "Points lost to transfer hits, ranked highest to lowest",
    "position_breakdown":"Defence / midfield / attack points per manager",
    "consistency":       "Mean weekly score with high/low range and standard deviation",
    "chip_bench_boost":  "Best Bench Boost returns per manager",
    "chip_triple_captain":"Best Triple Captain returns per manager",
    "chip_free_hit":     "Best Free Hit returns per manager",
    "chip_wildcard":     "Best Wildcard returns per manager",
    "weekly_scores":     "Line chart of points scored each gameweek",
    "league_position":   "Line chart of mini-league position each gameweek",
    "cumulative_points": "Running total points race across the season",
}

CHART_NAMES: Tuple[str, ...] = tuple(CHART_DESCRIPTIONS.keys())


def build_chart_dispatch(
    league_id: int,
    gameweeks: List[int],
    config: LeagueConfig,
    output_dir: Path,
    league_name: str,
    season: Optional[str] = None,
) -> Dict[str, Callable[[], None]]:
    """
    Build the chart-name → render-callable dispatch dict.

    Each value is a zero-arg lambda that renders one chart to a PNG inside
    `output_dir`. Stats and timeseries data are calculated lazily on first
    chart access so that single-chart renders (CLI --chart) don't pay for
    everything.

    Args:
        league_id:   FPL league ID.
        gameweeks:   Sorted list of gameweeks included in the render.
        config:      Loaded LeagueConfig.
        output_dir:  Destination directory for PNGs.
        league_name: Display name for the league (config override or API name).
        season:      Season label like "2025/26"; derived if None.
    """
    from .. import stats as stats_module
    from .. import stats_timeseries

    first_gw, last_gw = gameweeks[0], gameweeks[-1]
    subtitle = f"{league_name}  ·  GW{first_gw}–{last_gw}"

    # Memoised cache so callers that fetch multiple charts pay once
    cache: Dict[str, object] = {}

    def season_stats() -> dict:
        if "season_stats" not in cache:
            click.echo("  Calculating season statistics...")
            cache["season_stats"] = stats_module.calculate_season_statistics(
                league_id, gameweeks
            )
        return cache["season_stats"]  # type: ignore[return-value]

    def timeseries() -> dict:
        if "timeseries" not in cache:
            click.echo("  Calculating time series data...")
            cache["timeseries"] = stats_timeseries.calculate_all_timeseries(
                league_id, gameweeks
            )
        return cache["timeseries"]  # type: ignore[return-value]

    def all_manager_names() -> List[str]:
        if "all_manager_names" not in cache:
            cache["all_manager_names"] = _get_all_manager_names(
                league_id, gameweeks, stats_module
            )
        return cache["all_manager_names"]  # type: ignore[return-value]

    def s() -> dict:
        return season_stats()["stats"]

    chip_specs = [
        ("chip_bench_boost",    "Bench Boost",     "bench_boost",    False),
        ("chip_triple_captain", "Triple Captain",  "triple_captain", True),
        ("chip_free_hit",       "Free Hit",        "free_hit",       False),
        ("chip_wildcard",       "Wildcard",        "wildcard",       False),
    ]

    dispatch: Dict[str, Callable[[], None]] = {
        "legend": lambda: render_legend(
            config=config,
            league_name=league_name,
            gameweek_range=(first_gw, last_gw),
            season=season,
            output_path=output_dir / "legend.png",
        ),
        "wins_losses": lambda: render_wins_losses_bar(
            wins_losses=timeseries()["wins_losses"],
            total_gameweeks=len(gameweeks),
            config=config,
            output_path=output_dir / "wins_losses.png",
            subtitle=subtitle,
        ),
        "bench_points": lambda: render_ranked_bar(
            title="Bench Points Left on Bench",
            data=s()["highest_bench_points"]["totals"],
            config=config,
            output_path=output_dir / "bench_points.png",
            xlabel="Points",
            higher_is_worse=False,
            subtitle=subtitle,
        ),
        "transfer_costs": lambda: render_ranked_bar(
            title="Transfer Costs (Points Lost to Hits)",
            data=s()["most_transfer_cost"]["totals"],
            config=config,
            output_path=output_dir / "transfer_costs.png",
            xlabel="Points Lost",
            higher_is_worse=True,
            subtitle=subtitle,
        ),
        "position_breakdown": lambda: render_position_breakdown(
            position_data=s()["best_position_scores"],
            config=config,
            output_path=output_dir / "position_breakdown.png",
            subtitle=subtitle,
        ),
        "consistency": lambda: render_consistency_bar(
            consistency=timeseries()["consistency"],
            config=config,
            output_path=output_dir / "consistency.png",
            subtitle=subtitle,
        ),
        "weekly_scores": lambda: render_weekly_scores(
            series=timeseries()["weekly_scores"],
            config=config,
            output_path=output_dir / "weekly_scores.png",
            subtitle=subtitle,
        ),
        "league_position": lambda: render_league_position(
            series=timeseries()["weekly_rankings"],
            config=config,
            output_path=output_dir / "league_position.png",
            subtitle=subtitle,
        ),
        "cumulative_points": lambda: render_cumulative_points(
            series=timeseries()["cumulative_points"],
            config=config,
            output_path=output_dir / "cumulative_points.png",
            subtitle=subtitle,
        ),
    }

    for key, name, data_key, is_tc in chip_specs:
        # Bind loop variables explicitly so each lambda gets its own values.
        dispatch[key] = (
            lambda name=name, data_key=data_key, is_tc=is_tc, key=key: render_chip_chart(
                chip_name=name,
                raw_data=s()["best_chip_returns"].get(data_key, []),
                all_manager_names=all_manager_names(),
                config=config,
                output_path=output_dir / f"{key}.png",
                is_triple_captain=is_tc,
                subtitle=subtitle,
            )
        )

    # Surface dispatch keys in the canonical order from CHART_DESCRIPTIONS,
    # which is also the order CLI --list and the help text expects.
    return {name: dispatch[name] for name in CHART_NAMES}


def render_all(
    league_id: int,
    gameweeks: List[int],
    config: LeagueConfig,
    output_dir: Path,
    league_name: str,
    season: Optional[str] = None,
) -> None:
    """Render every chart in output_dir, with progress output per chart."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dispatch = build_chart_dispatch(
        league_id, gameweeks, config, output_dir, league_name, season
    )
    for name, render_fn in dispatch.items():
        click.echo(f"  Rendering {name}.png...")
        render_fn()
    click.echo(f"\n  Done! All graphs saved to {output_dir}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_all_manager_names(
    league_id: int,
    gameweeks: List[int],
    stats_module,
) -> List[str]:
    """
    Return the FPL player_names of all managers in the league.

    Reads from the first available gameweek's standings cache.
    Falls back to an empty list if no data is available.
    """
    for gameweek in gameweeks:
        gw_data = stats_module.load_gameweek_data(league_id, gameweek)
        if gw_data:
            standings = gw_data["league_data"]["standings"]["results"]
            return [m["player_name"] for m in standings]
    return []
