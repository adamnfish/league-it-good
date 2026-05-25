"""
Ranked Bar Charts

Renders simple horizontal bar charts for aggregate season stats:
    - Bench points left on bench (ranked, single bar per manager)
    - Transfer costs / hits taken (ranked, single bar per manager)
    - Positional points breakdown — defence, midfield, attack (grouped)
    - Score consistency — standard deviation bar with high/low range markers
    - Gameweek wins, losses, mid-table (stacked bar, fixed total width)

All charts share the same visual language from render.py: dark background,
Outfit font, manager avatar at the bar tip, grey background track.
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


# Type aliases
ManagerName = str
RankedData = List[Tuple[ManagerName, int]]  # [(name, value), ...] sorted desc


# ---------------------------------------------------------------------------
# Simple ranked bar chart
# ---------------------------------------------------------------------------

def render_ranked_bar(
    title: str,
    data: RankedData,
    config: LeagueConfig,
    output_path: Path,
    xlabel: str = "Points",
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render a single horizontal bar per manager, sorted by value.

    Bars always use the manager's theme colour.

    Args:
        title:       Chart title shown top-left in accent colour.
        data:        List of (fpl_name, value) tuples, sorted descending.
        config:      League config for display names, colours, avatars.
        output_path: Destination PNG path.
        xlabel:      X-axis label.
    """
    if not data:
        return

    n_managers = len(data)
    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(
        fig, ax, title=title, xlabel=xlabel, subtitle=subtitle, description=description,
    )

    max_value = max(v for _, v in data) if data else 1
    x_max = max(max_value * (1 + render.X_PADDING_FRACTION), 10)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    # Values on these charts are always integers (points, hit costs) — avoid
    # matplotlib's default 0.0/2.5/5.0 fractional ticks.
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

    for i, (fpl_name, value) in enumerate(data):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_BAR,
        )

        # Background track
        render.draw_bar_track(ax, y=i, width=x_max)

        # Bar
        ax.barh(
            i, value,
            height=render.BAR_HEIGHT,
            color=colour,
            zorder=2,
        )

        # Value label — inside if wide enough, otherwise outside
        render.draw_segment_label(
            ax,
            x_centre=value / 2,
            y=i,
            label=str(value),
            segment_width=value,
            x_max=x_max,
        )

        # Avatar at bar tip
        render.place_avatar(ax, x=value, y=i, avatar_rgba=avatar)

        # Manager name
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    render.save_figure(fig, output_path)


# ---------------------------------------------------------------------------
# Consistency bar chart
# ---------------------------------------------------------------------------

def render_consistency_bar(
    consistency: Dict[ManagerName, Dict[str, float]],
    config: LeagueConfig,
    output_path: Path,
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """
    Render a bar chart showing scoring consistency per manager.

    Each manager gets:
      - A bar of length equal to their mean weekly score (manager colour)
      - A horizontal range line from their lowest to highest single GW score,
        overlaid on the bar, in white at low opacity
      - A small dot marker at both the low and high extremes

    Sorted by standard deviation ascending (most consistent at top).

    Args:
        consistency: Output of calculate_score_consistency —
                     {fpl_name: {'mean': float, 'std': float,
                                 'high': float, 'low': float, 'range': float}}
        config:      League config.
        output_path: Destination PNG path.
    """
    if not consistency:
        return

    # Sort by mean descending — highest average weekly score at the top
    sorted_managers = sorted(
        consistency.items(),
        key=lambda item: item[1]["mean"],
        reverse=True,
    )

    n_managers = len(sorted_managers)
    fig, ax = render.make_bar_figure(n_managers)
    render.apply_bar_style(
        fig, ax,
        title="Scoring Consistency",
        xlabel="Points",
        subtitle=subtitle,
        description=description,
    )

    max_high = max(v["high"] for _, v in sorted_managers) if sorted_managers else 1
    x_max = max_high * (1 + render.X_PADDING_FRACTION)
    ax.set_xlim(-(x_max * 0.02), x_max)
    ax.set_yticks(list(range(n_managers)))
    ax.set_yticklabels([])
    ax.invert_yaxis()

    for i, (fpl_name, stats) in enumerate(sorted_managers):
        manager_cfg = config.get_manager(fpl_name)
        colour = manager_cfg.colour if manager_cfg else "#888888"
        display_name = manager_cfg.display_name if manager_cfg else fpl_name
        avatar = render.load_avatar(
            manager_cfg.avatar_path if manager_cfg else None,
            display_name,
            colour,
            size=render.AVATAR_SIZE_BAR,
            border_colour=colour,
            border_ratio=render.AVATAR_BORDER_RATIO_BAR,
        )

        mean  = stats["mean"]
        high  = stats["high"]
        low   = stats["low"]

        render.draw_bar_track(ax, y=i, width=x_max)

        # Mean bar
        ax.barh(
            i, mean,
            height=render.BAR_HEIGHT,
            color=colour,
            zorder=2,
        )

        # High/low range line overlaid across the bar
        ax.plot(
            [low, high], [i, i],
            color="white",
            linewidth=2,
            alpha=0.4,
            zorder=3,
            solid_capstyle="round",
        )

        # Dot markers at extremes
        ax.plot(
            [low, high], [i, i],
            "o",
            color="white",
            markersize=5,
            alpha=0.7,
            zorder=4,
        )

        render.place_avatar(ax, x=mean, y=i, avatar_rgba=avatar)
        render.draw_manager_label(ax, y=i, display_name=display_name,
                                  x_offset=-(x_max * 0.02))

    # Subtitle explaining the range line
    fig.text(
        0.04, 0.02,
        "Bar = mean score  ·  Line = best to worst single gameweek",
        color=render.TEXT_MUTED,
        fontsize=8,
        va="bottom",
        transform=fig.transFigure,
    )

    plt.tight_layout(rect=[0, 0.04, 1, 0.93])
    render.save_figure(fig, output_path)
