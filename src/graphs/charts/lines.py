"""
Line Charts (Time Series)

Renders week-by-week line charts for the season:
    - Weekly scores       — raw points each gameweek per manager
    - League position     — mini-league rank at end of each gameweek (inverted y)
    - Cumulative points   — running total, the classic season race chart

All three share a common rendering core. Each manager gets:
    - A line with a glow effect (plotted twice: thick+transparent, then crisp)
    - Small dot markers at each gameweek data point
    - A circular avatar at the final data point, acting as the line label
    - A small text annotation of the final value next to the avatar

The charts are intentionally wide (FIGURE_WIDTH) and modestly tall so the
lines have room to breathe horizontally.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from ..config import LeagueConfig
from .. import render


# Type aliases — match stats_timeseries output shapes
ManagerName = str
WeeklySeries = Dict[ManagerName, List[Tuple[int, int]]]   # {name: [(gw, value), ...]}
RankSeries   = Dict[ManagerName, List[Tuple[int, int]]]   # {name: [(gw, rank), ...]}


# ---------------------------------------------------------------------------
# Shared line rendering core
# ---------------------------------------------------------------------------

def _render_line_chart(
    title: str,
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    ylabel: str,
    invert_y: bool = False,
    y_tick_formatter: Optional[ticker.Formatter] = None,
    final_value_fmt: str = "{v}",
    subtitle: Optional[str] = None,
) -> None:
    """
    Core renderer shared by all three line chart types.

    Args:
        title:             Chart title, shown top-left in accent colour.
        series:            {manager_fpl_name: [(gameweek, value), ...]}
                           Each manager's list must be sorted chronologically.
        config:            League config for display names, colours, avatars.
        output_path:       Destination PNG path.
        ylabel:            Y-axis label.
        invert_y:          When True, the y-axis is inverted so rank 1 sits
                           at the top (used for the league position chart).
        y_tick_formatter:  Optional custom tick formatter for the y-axis.
        final_value_fmt:   Format string for the end-of-line annotation.
                           Use "{v}" as the placeholder for the value,
                           e.g. "{v}pts" or "#{v}".
    """
    if not series:
        return

    # Figure is wider than bar charts — lines need horizontal room
    fig, ax = plt.subplots(figsize=(render.FIGURE_WIDTH, 7))
    render.apply_line_style(fig, ax, title=title, ylabel=ylabel, subtitle=subtitle)

    all_gameweeks = sorted({gw for pts in series.values() for gw, _ in pts})
    if not all_gameweeks:
        plt.close(fig)
        return

    ax.set_xticks(all_gameweeks)
    ax.set_xlim(all_gameweeks[0] - 0.5, all_gameweeks[-1] + 1.5)

    if y_tick_formatter:
        ax.yaxis.set_major_formatter(y_tick_formatter)

    if invert_y:
        ax.invert_yaxis()

    # Sort managers so the highest final value is drawn last (on top)
    # For inverted axes (rankings) lowest final value = best = drawn on top
    def final_value(item: tuple) -> int:
        _, pts = item
        return pts[-1][1] if pts else 0

    draw_order = sorted(series.items(), key=final_value, reverse=not invert_y)

    for fpl_name, data_points in draw_order:
        if not data_points:
            continue

        manager_cfg = config.get_manager(fpl_name)
        colour      = manager_cfg.colour      if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar      = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_LINE,
        )

        gws    = [gw for gw, _ in data_points]
        values = [v  for _,  v in data_points]

        # Glow pass — thick, low alpha
        ax.plot(
            gws, values,
            color=colour,
            linewidth=render.GLOW_WIDTH,
            alpha=render.GLOW_ALPHA,
            zorder=2,
            solid_capstyle="round",
        )

        # Crisp line pass
        ax.plot(
            gws, values,
            color=colour,
            linewidth=render.LINE_WIDTH,
            alpha=1.0,
            zorder=3,
            solid_capstyle="round",
        )

        # Dot markers at each data point (filled with background colour for
        # a hollow-centre effect)
        ax.plot(
            gws, values,
            "o",
            color=colour,
            markersize=5,
            markerfacecolor=render.BACKGROUND,
            markeredgewidth=1.5,
            zorder=4,
        )

        # Avatar at the final data point
        final_gw    = gws[-1]
        final_value_v = values[-1]
        render.place_avatar(
            ax,
            x=final_gw,
            y=final_value_v,
            avatar_rgba=avatar,
            zoom=render.AVATAR_ZOOM_LINE,
        )

        # Final value annotation just to the right of the avatar
        # Offset in data units: ~0.6 gameweeks right, nudged up slightly
        ax.annotate(
            final_value_fmt.format(v=final_value_v),
            xy=(final_gw, final_value_v),
            xytext=(final_gw + 0.55, final_value_v),
            va="center",
            ha="left",
            color=colour,
            fontsize=8,
            fontweight="bold",
            zorder=6,
        )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Public chart functions
# ---------------------------------------------------------------------------

def render_weekly_scores(
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a line chart of raw points scored each gameweek per manager.

    Useful for spotting form runs, disasters, and chip weeks. Lines that
    spike dramatically are often chip weeks or captaincy differentials.

    Args:
        series:      Output of calculate_weekly_scores —
                     {fpl_name: [(gameweek, points), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    _render_line_chart(
        title="Weekly Scores",
        series=series,
        config=config,
        output_path=output_path,
        ylabel="Points",
        invert_y=False,
        final_value_fmt="{v}pts",
        subtitle=subtitle,
    )


def render_league_position(
    series: RankSeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a line chart of mini-league position at the end of each gameweek.

    Y-axis is inverted so rank 1 sits at the top. Integer ticks only.
    The number of managers in the league is inferred from the maximum rank
    seen in the data, so the y-axis always spans 1 → league size.

    Args:
        series:      Output of calculate_weekly_rankings —
                     {fpl_name: [(gameweek, rank), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    if not series:
        return

    # Y-axis: 1 at top, n_managers at bottom
    all_ranks = [rank for pts in series.values() for _, rank in pts]
    n_managers = max(all_ranks) if all_ranks else 1

    fig, ax = plt.subplots(figsize=(render.FIGURE_WIDTH, 7))
    render.apply_line_style(fig, ax, title="League Position", ylabel="Position", subtitle=subtitle)

    all_gameweeks = sorted({gw for pts in series.values() for gw, _ in pts})
    if not all_gameweeks:
        plt.close(fig)
        return

    ax.set_xticks(all_gameweeks)
    ax.set_xlim(all_gameweeks[0] - 0.5, all_gameweeks[-1] + 1.5)

    # Integer ticks, 1 at top
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_ylim(n_managers + 0.5, 0.5)   # inverted: 1 at top

    # Draw managers with worst final position first (they end up behind)
    def final_rank(item: tuple) -> int:
        _, pts = item
        return pts[-1][1] if pts else n_managers + 1

    draw_order = sorted(series.items(), key=final_rank, reverse=True)

    for fpl_name, data_points in draw_order:
        if not data_points:
            continue

        manager_cfg  = config.get_manager(fpl_name)
        colour       = manager_cfg.colour       if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar       = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_LINE,
        )

        gws    = [gw   for gw, _ in data_points]
        values = [rank for _,  rank in data_points]

        ax.plot(gws, values, color=colour,
                linewidth=render.GLOW_WIDTH, alpha=render.GLOW_ALPHA,
                zorder=2, solid_capstyle="round")

        ax.plot(gws, values, color=colour,
                linewidth=render.LINE_WIDTH, alpha=1.0,
                zorder=3, solid_capstyle="round")

        ax.plot(gws, values, "o", color=colour,
                markersize=5, markerfacecolor=render.BACKGROUND,
                markeredgewidth=1.5, zorder=4)

        final_gw   = gws[-1]
        final_rank_v = values[-1]
        render.place_avatar(ax, x=final_gw, y=final_rank_v,
                            avatar_rgba=avatar, zoom=render.AVATAR_ZOOM_LINE)

        # Ordinal suffix for rank annotation: 1st, 2nd, 3rd, 4th…
        suffix = _ordinal_suffix(final_rank_v)
        ax.annotate(
            f"{final_rank_v}{suffix}",
            xy=(final_gw, final_rank_v),
            xytext=(final_gw + 0.55, final_rank_v),
            va="center",
            ha="left",
            color=colour,
            fontsize=8,
            fontweight="bold",
            zorder=6,
        )

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


def render_cumulative_points(
    series: WeeklySeries,
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
) -> None:
    """
    Render a running total points race chart — the classic season arc.

    Lines only ever go up, so the visual spread between managers widens
    over the season. The manager leading at GW38 ends up with the highest
    line, providing a clear winner narrative.

    Args:
        series:      Output of calculate_cumulative_points —
                     {fpl_name: [(gameweek, cumulative_points), ...]}
        config:      League config.
        output_path: Destination PNG path.
    """
    _render_line_chart(
        title="Cumulative Points",
        series=series,
        config=config,
        output_path=output_path,
        ylabel="Total Points",
        invert_y=False,
        final_value_fmt="{v}pts",
        subtitle=subtitle,
    )


# ---------------------------------------------------------------------------
# Convenience: render all three line charts
# ---------------------------------------------------------------------------

def render_all_line_charts(
    timeseries: dict,
    config: LeagueConfig,
    output_dir: Path,
) -> None:
    """
    Render all three line charts from the output of calculate_all_timeseries.

    Output files:
        weekly_scores.png
        league_position.png
        cumulative_points.png

    Args:
        timeseries:  Output of calculate_all_timeseries — dict with keys
                     'weekly_scores', 'weekly_rankings', 'cumulative_points'.
        config:      League config.
        output_dir:  Directory to write PNGs into.
    """
    render_weekly_scores(
        series=timeseries.get("weekly_scores", {}),
        config=config,
        output_path=output_dir / "weekly_scores.png",
    )
    render_league_position(
        series=timeseries.get("weekly_rankings", {}),
        config=config,
        output_path=output_dir / "league_position.png",
    )
    render_cumulative_points(
        series=timeseries.get("cumulative_points", {}),
        config=config,
        output_path=output_dir / "cumulative_points.png",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ordinal_suffix(n: int) -> str:
    """Return the ordinal suffix for an integer: 1→'st', 2→'nd', 3→'rd', 4→'th'."""
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
